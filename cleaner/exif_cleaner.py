"""Image Metadata Cleaner — core library.

Privacy-first cleaning: rebuilds pixel data into a fresh image so no
EXIF / GPS / ICC / XMP / comment chunks survive. Never touches the input file.

Public API
----------
``analyze_metadata(path)``      read-only metadata report
``clean_metadata(src, dst, …)`` one image -> one clean copy
``batch_clean(paths, …)``       many images, per-file status, never raises
``add_watermark(img, text, …)`` semi-transparent, RTL/LTR aware watermark
"""

from __future__ import annotations

import contextlib
import os
import re
from collections.abc import Callable, Sequence
from typing import Any

import piexif
from PIL import ExifTags, Image, ImageDraw, ImageFont, ImageOps, ImageSequence

# --------------------------------------------------------------------------
# Optional HEIC/HEIF (iPhone) support. Pillow cannot decode HEIC on its own.
# --------------------------------------------------------------------------
_HEIF_AVAILABLE = False
try:  # pragma: no cover - depends on the optional wheel being installed
    import pillow_heif

    pillow_heif.register_heif_opener()
    _HEIF_AVAILABLE = True
except Exception:  # pragma: no cover
    _HEIF_AVAILABLE = False

# --------------------------------------------------------------------------
# DoS / sanity guards
# --------------------------------------------------------------------------
MAX_DIMENSION = 10000  # max width/height for --resize
MAX_PIXELS = 50_000_000  # max output pixel count (~50MP)
MAX_WATERMARK_LEN = 200

# Pillow's decompression-bomb guard (Image.MAX_IMAGE_PIXELS) stays at its
# default: it is the only thing that protects *decoding*. We deliberately do
# not re-assign it to itself (a no-op that used to look like a guard), and
# PIL.Image.LOAD_TRUNCATED_IMAGES already defaults to False, so truncated
# files raise instead of being half-decoded. MAX_PIXELS below guards output.

SUPPORTED_EXTENSIONS: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".webp")
_EXT_TO_FORMAT: dict[str, str] = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
}
if _HEIF_AVAILABLE:  # pragma: no cover - optional
    SUPPORTED_EXTENSIONS = (*SUPPORTED_EXTENSIONS, ".heic", ".heif")
    _EXT_TO_FORMAT.update({".heic": "HEIF", ".heif": "HEIF"})

# Pillow reports single frames of a multi-picture JPEG as "MPO".
_FORMAT_ALIASES = {"MPO": "JPEG", "JPG": "JPEG", "HEIF": "HEIF", "AVIF": "AVIF"}
SUPPORTED_FORMATS: tuple[str, ...] = ("JPEG", "PNG", "WEBP") + (("HEIF",) if _HEIF_AVAILABLE else ())


# --------------------------------------------------------------------------
# Metadata classification
#
# `info` entries Pillow writes for *every* file of that type (JFIF headers,
# pHYs density, animation timings …). They carry no personal information and
# must not make a perfectly clean file look "dirty".
# --------------------------------------------------------------------------
_TECHNICAL_KEYS = frozenset(
    {
        "jfif",
        "jfif_version",
        "jfif_unit",
        "jfif_density",
        "interlace",
        "transparency",
        "dpi",
        "gamma",
        "duration",
        "loop",
        "background",
        "extension",
        "mp",
        "srgb",
        "bits",
        "version",
        "timestamp",  # WebP frame timestamp (container field, not user data)
    }
)

# Chunks that are always worth shouting about.
_PRIVACY_KEYS = frozenset(
    {
        "exif",
        "icc_profile",
        "iccprofile",
        "xmp",
        "xml:com.adobe.xmp",
        "comment",
        "iptc",
        "photoshop",
        "adobe",
        "author",
        "software",
        "description",
        "copyright",
        "title",
        "creation_time",
        "location",
    }
)

# PNG/WebP textual chunk prefixes that hold user data.
_TEXT_CHUNK_HINTS = ("text", "ztext", "itxt", "comment", "description", "software", "author", "copyright")

_IMAGE_CHUNK_KEYS = frozenset(
    {
        "exif",
        "icc_profile",
        "iccprofile",
        "xmp",
        "xml:com.adobe.xmp",
        "comment",
        "iptc",
        "photoshop",
        "adobe",
    }
)


def _resolve_tag_name(tag_id: int) -> str:
    """Resolve a numeric EXIF tag id to a human readable name."""
    return ExifTags.TAGS.get(tag_id, f"Unknown_{tag_id}")


def _is_technical(key: str) -> bool:
    return str(key).lower() in _TECHNICAL_KEYS


def _is_metadata_key(key: str) -> bool:
    """Fail-closed: anything not on the technical allow-list counts as metadata."""
    if _is_technical(key):
        return False
    kl = str(key).lower()
    if kl in _PRIVACY_KEYS or kl in _IMAGE_CHUNK_KEYS:
        return True
    # Unknown / custom chunk (PNG tEXt, WebP XMP, vendor blobs …): report it.
    return True


def _safe_text(value: Any, limit: int = 200) -> str:
    try:
        if isinstance(value, (bytes, bytearray)):
            return f"<binary {len(value)} bytes>"
        return str(value)[:limit]
    except Exception:
        return "<unprintable>"


def _rat_to_float(value: Any) -> float:
    try:
        if isinstance(value, (tuple, list)) and len(value) == 2:
            num, den = value
            return float(num) / float(den) if den else 0.0
        return float(value)
    except Exception:
        return 0.0


def _dms_to_decimal(dms: Sequence[Any], ref: str) -> float | None:
    try:
        d = _rat_to_float(dms[0])
        m = _rat_to_float(dms[1])
        s = _rat_to_float(dms[2])
    except Exception:
        return None
    val = d + m / 60.0 + s / 3600.0
    if str(ref).upper() in ("S", "W"):
        val = -val
    return round(val, 6)


def _exif_to_dict(exif: Any) -> dict[str, str]:
    """Flatten an EXIF object (0th + Exif + Interop IFDs) to readable pairs."""
    out: dict[str, str] = {}
    if not exif:
        return out
    try:
        items = list(exif.items())
    except Exception:
        return out
    for tag_id, value in items:
        name = _resolve_tag_name(int(tag_id)) if str(tag_id).isdigit() or isinstance(tag_id, int) else str(tag_id)
        out[str(name)] = _safe_text(value)
    # Nested IFDs are not exposed by .items(): read them explicitly.
    for ifd_id in (0x8769, 0xA005):  # Exif IFD, Interop IFD
        try:
            sub = exif.get_ifd(ifd_id)
        except Exception:
            continue
        for tag_id, value in (sub or {}).items():
            out.setdefault(_resolve_tag_name(int(tag_id)), _safe_text(value))
    return out


def _gps_from_piexif(image_path: str) -> tuple[dict[str, str], dict[str, Any]]:
    """Read the GPS IFD with human readable keys. Returns (readable, raw)."""
    human: dict[str, str] = {}
    raw: dict[str, Any] = {}
    try:
        data = piexif.load(image_path)
    except Exception:
        return human, raw
    if not isinstance(data, dict):
        return human, raw
    gps = data.get("GPS") or {}
    if not gps:
        return human, raw
    try:
        from piexif import GPSIFD
    except Exception:  # pragma: no cover
        GPSIFD = None  # type: ignore[assignment]
    for k, v in gps.items():
        name = f"GPS_{k}"
        if GPSIFD is not None:
            name = next(
                (n for n, c in vars(GPSIFD).items() if c == k and not n.startswith("_")),
                name,
            )
        human[str(name)] = _safe_text(v)
        raw[str(name)] = v
    return human, raw


def _gps_decimal(gps_raw: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    lat = gps_raw.get("GPSLatitude")
    lon = gps_raw.get("GPSLongitude")
    if lat and lon:
        lat_ref = gps_raw.get("GPSLatitudeRef", "N")
        lon_ref = gps_raw.get("GPSLongitudeRef", "E")
        if isinstance(lat_ref, bytes):
            lat_ref = lat_ref.decode("ascii", "ignore")
        if isinstance(lon_ref, bytes):
            lon_ref = lon_ref.decode("ascii", "ignore")
        dlat = _dms_to_decimal(lat, lat_ref)
        dlon = _dms_to_decimal(lon, lon_ref)
        if dlat is not None and dlon is not None:
            out = {"lat": dlat, "lon": dlon}
    alt = gps_raw.get("GPSAltitude")
    if alt is not None:
        with contextlib.suppress(Exception):
            out["alt"] = round(_rat_to_float(alt), 2)
    return out


def analyze_metadata(image_path: str) -> dict[str, Any]:
    """Analyze the metadata in an image (strictly read-only).

    Returns a dict with ``has_metadata`` (privacy-relevant metadata only),
    ``details`` (everything found, for transparency), ``metadata`` (privacy
    relevant subset), ``technical`` (harmless container headers), ``exif``,
    ``gps``, ``gps_decimal``, ``format``, ``size``, ``mode``, ``file_size``.
    On failure returns ``{"error": ...}``.
    """
    try:
        if not os.path.isfile(image_path):
            return {"error": f"File not found: {image_path}"}

        with Image.open(image_path) as img:
            fmt = _FORMAT_ALIASES.get(str(img.format or "").upper(), str(img.format or "UNKNOWN"))
            n_frames = int(getattr(img, "n_frames", 1) or 1)
            is_animated = bool(getattr(img, "is_animated", False)) and n_frames > 1
            durations: list[Any] = []
            if is_animated:
                for i in range(n_frames):
                    try:
                        img.seek(i)
                        durations.append(img.info.get("duration"))
                    except Exception:
                        break
                with contextlib.suppress(Exception):
                    img.seek(0)

            img.load()  # force parsing so truncated files fail here, not later

            details: dict[str, Any] = {}
            technical: dict[str, Any] = {}

            # --- EXIF via the public API (never _getexif) -------------------
            try:
                raw_exif = img.getexif()
            except Exception:
                raw_exif = None
            exif_dict = _exif_to_dict(raw_exif)
            if exif_dict:
                details["exif"] = exif_dict

            # --- GPS via piexif (PNG/WebP simply fail here, that's fine) ----
            gps_human, gps_raw = _gps_from_piexif(image_path)
            if gps_human:
                details["gps"] = gps_human

            # --- Everything else Pillow exposes through `info` --------------
            row_dpi = None
            for key, value in (img.info or {}).items():
                kl = str(key).lower()
                if kl == "exif":
                    continue  # already reported above
                if kl in ("icc_profile", "iccprofile"):
                    details["icc_profile"] = (
                        f"<binary {len(value)} bytes>" if isinstance(value, (bytes, bytearray)) else _safe_text(value)
                    )
                    continue
                if kl in ("duration",):
                    continue
                if kl in ("dpi", "jfif_density"):
                    row_dpi = value
                    technical[str(key)] = _safe_text(value)
                    continue
                if _is_technical(str(key)):
                    technical[str(key)] = _safe_text(value)
                    continue
                if kl in ("xmp", "xml:com.adobe.xmp"):
                    details["xmp"] = _safe_text(value, 400)
                    continue
                details[str(key)] = _safe_text(value)

            if durations:
                technical["duration"] = _safe_text(durations)

            merged: dict[str, Any] = {}
            merged.update(details)
            merged.update(technical)

            metadata_view = {k: v for k, v in merged.items() if _is_metadata_key(k)}
            has_meta = bool(metadata_view)

            gps_decimal = _gps_decimal(gps_raw)

            try:
                file_size = os.path.getsize(image_path)
            except OSError:
                file_size = None

            return {
                "has_metadata": has_meta,
                "has_gps": bool(gps_human) and bool(gps_decimal),
                "gps_decimal": gps_decimal,
                "details": merged,
                "metadata": metadata_view,
                "technical": technical,
                "exif": exif_dict,
                "gps": gps_human,
                "dpi": row_dpi,
                "format": fmt,
                "size": tuple(img.size),
                "mode": img.mode,
                "file_size": file_size,
                "is_animated": is_animated,
                "frames": n_frames,
                "extensions_supported": list(SUPPORTED_EXTENSIONS),
            }
    except FileNotFoundError:
        return {"error": f"File not found: {image_path}"}
    except Image.DecompressionBombError as e:
        return {"error": f"Image too large to process safely: {e}"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


# --------------------------------------------------------------------------
# Watermark (RTL / Persian aware)
# --------------------------------------------------------------------------
_RTL_RE = re.compile("[\u0590-\u05ff\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb1d-\ufdff\ufe70-\ufeff]")
_RAQM = bool(getattr(getattr(ImageFont, "core", None), "HAVE_RAQM", False))

_LTR_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:\\Windows\\Fonts\\segoeuib.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
)
# Fonts with real Persian/Arabic coverage, tried first for RTL text.
_RTL_FONTS = (
    "C:\\Windows\\Fonts\\tahoma.ttf",
    "C:\\Windows\\Fonts\\segoeui.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabicUI-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Tahoma.ttf",
)


def has_rtl(text: str) -> bool:
    """True when the string contains RTL (Arabic/Hebrew) characters."""
    return bool(_RTL_RE.search(text or ""))


def _shape_text(text: str) -> tuple[str, dict[str, Any]]:
    """Return text plus the drawing kwargs needed for correct RTL rendering.

    With libraqm (FreeType + HarfBuzz, present in official Pillow wheels) we let
    Pillow shape and bidi-reorder natively. Otherwise we fall back to
    arabic_reshaper + python-bidi when they happen to be installed.
    """
    if not has_rtl(text):
        return text, {}
    if _RAQM:
        return text, {"direction": "rtl", "language": "fa"}
    try:  # pragma: no cover - optional dependency
        import arabic_reshaper
        from bidi.algorithm import get_display

        return get_display(arabic_reshaper.reshape(text)), {}
    except Exception:
        return text, {}


def _load_font(size: int, rtl: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a usable font cross-platform, with graceful fallback."""
    candidates = (_RTL_FONTS + _LTR_FONTS) if rtl else (_LTR_FONTS + _RTL_FONTS)
    for path in candidates:
        try:
            if os.path.isfile(path):
                return ImageFont.truetype(path, size)
        except Exception:
            continue
    for name in ("DejaVuSans-Bold.ttf", "Tahoma.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _measure(draw: ImageDraw.ImageDraw, text: str, font, kwargs: dict[str, Any]) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font, **kwargs)
    return int(bbox[2] - bbox[0]), int(bbox[3] - bbox[1])


def add_watermark(
    img: Image.Image,
    text: str,
    opacity: float = 0.35,
    position: str = "bottom-right",
) -> Image.Image:
    """Add a semi-transparent watermark. RTL text is shaped correctly.

    ``position`` is one of bottom-right (default), bottom-left, bottom-center,
    top-right, top-left, top-center, center.
    """
    if not text or not str(text).strip():
        raise ValueError("Watermark text must be non-empty")
    text = str(text).strip()
    if len(text) > MAX_WATERMARK_LEN:
        raise ValueError(f"Watermark too long (max {MAX_WATERMARK_LEN} chars)")
    try:
        opacity = float(opacity)
    except Exception as err:
        raise ValueError("Opacity must be a number in (0, 1]") from err
    if not (0.0 < opacity <= 1.0):
        raise ValueError("Opacity must be in (0, 1]")
    valid_positions = {
        "bottom-right",
        "bottom-left",
        "bottom-center",
        "top-right",
        "top-left",
        "top-center",
        "center",
    }
    position = str(position or "bottom-right").lower()
    if position not in valid_positions:
        raise ValueError(f"position must be one of {sorted(valid_positions)}")

    w, h = img.size
    if w <= 0 or h <= 0:
        raise ValueError("Invalid image dimensions")

    rtl = has_rtl(text)
    rendered, draw_kwargs = _shape_text(text)

    font_size = max(12, min(w, h) // 20)
    font = _load_font(font_size, rtl=rtl)

    base = img.convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    tw, th = _measure(draw, rendered, font, draw_kwargs)
    while tw > w - 20 and font_size > 10:
        font_size = max(10, font_size - 2)
        font = _load_font(font_size, rtl=rtl)
        tw, th = _measure(draw, rendered, font, draw_kwargs)

    margin = max(8, min(w, h) // 40)
    if position.endswith("left"):
        x = margin
    elif position.endswith("center"):
        x = max(margin, (w - tw) // 2)
    else:
        x = max(margin, w - tw - margin)
    if position.startswith("top"):
        y = margin
    elif position.startswith("center"):
        y = max(margin, (h - th) // 2)
    else:
        y = max(margin, h - th - margin)

    alpha = int(255 * opacity)
    # Slight shadow for readability on bright backgrounds.
    draw.text((x + 1, y + 1), rendered, fill=(0, 0, 0, alpha), font=font, **draw_kwargs)
    draw.text((x, y), rendered, fill=(255, 255, 255, alpha), font=font, **draw_kwargs)

    out = Image.alpha_composite(base, layer)
    out.info.clear()
    return out


# --------------------------------------------------------------------------
# Validation helpers
# --------------------------------------------------------------------------
def _validate_resize(resize: tuple[int, int] | None) -> tuple[int, int] | None:
    if resize is None:
        return None
    if not isinstance(resize, (tuple, list)) or len(resize) != 2:
        raise ValueError("resize must be a (width, height) tuple")
    try:
        rw, rh = int(resize[0]), int(resize[1])
    except Exception as err:
        raise ValueError("resize dimensions must be integers") from err
    if rw <= 0 or rh <= 0:
        raise ValueError("resize dimensions must be positive (e.g. 800x600)")
    if rw > MAX_DIMENSION or rh > MAX_DIMENSION:
        raise ValueError(f"resize dimensions too large (max {MAX_DIMENSION}x{MAX_DIMENSION})")
    if rw * rh > MAX_PIXELS:
        raise ValueError(f"resize target too large (max ~{MAX_PIXELS // 1_000_000} megapixels)")
    return (rw, rh)


def _fit_within(size: tuple[int, int], box: tuple[int, int]) -> tuple[int, int]:
    """Scale ``size`` down to fit inside ``box``, keeping the aspect ratio.

    ``resize`` is a bounding box, not an exact output size: squashing a photo to
    the wrong shape distorts it, and enlarging a small photo adds no detail while
    making the file bigger. Both used to happen.
    """
    width, height = size
    max_width, max_height = box
    if width <= 0 or height <= 0:
        return size
    scale = min(max_width / width, max_height / height, 1.0)
    if scale >= 1.0:
        return (width, height)
    return (max(1, round(width * scale)), max(1, round(height * scale)))


def _validate_quality(quality: int) -> int:
    if isinstance(quality, bool) or not isinstance(quality, int) or not (1 <= quality <= 100):
        raise ValueError("quality must be an integer in 1..100")
    return quality


def _validate_opacity(opacity: float) -> float:
    try:
        value = float(opacity)
    except Exception as err:
        raise ValueError("opacity must be a number in (0, 1]") from err
    if not (0.0 < value <= 1.0):
        raise ValueError("opacity must be in (0, 1]")
    return value


def _normalize_format(fmt: str | None) -> str | None:
    if not fmt:
        return None
    return _FORMAT_ALIASES.get(str(fmt).upper(), str(fmt).upper())


def format_for_extension(output_path: str, fallback: str | None = None) -> str:
    """Resolve the save format from the output extension, else the source format."""
    ext = os.path.splitext(output_path)[1].lower()
    if ext in _EXT_TO_FORMAT:
        return _EXT_TO_FORMAT[ext]
    if ext and ext not in _EXT_TO_FORMAT:
        raise ValueError(f"Unsupported output extension '{ext}'. Supported: {' '.join(sorted(set(_EXT_TO_FORMAT)))}")
    src = _normalize_format(fallback)
    if src == "HEIF":
        return "JPEG"  # most useful default when re-encoding HEIC too not force HEIC
    if src in ("JPEG", "PNG", "WEBP"):
        return src
    return "PNG"


# Backwards-compatible private alias (old name kept for callers/tests).
_infer_save_format = format_for_extension


def _fresh_frame(img: Image.Image) -> Image.Image:
    """Copy one frame onto a brand new canvas — same pixels, zero metadata."""
    mode = img.mode
    if mode in ("P", "PA"):
        target = "RGBA" if img.info.get("transparency") is not None else "RGB"
    elif mode in ("LA", "La"):
        target = "LA"
    elif mode in ("RGB", "RGBA", "L", "I;16", "I;16B", "I;16L"):
        target = mode
    else:
        # CMYK, YCbCr, LAB, HSV, 1, I, F, exotic vendor modes: RGB is the only
        # universally safe container. Never fall back to img.copy(), which
        # would carry the `info` metadata dict along.
        target = "RGB"

    converted = img if img.mode == target else img.convert(target)
    fresh = Image.new(converted.mode, converted.size)
    if fresh.mode in ("RGBA", "LA"):
        fresh.paste(converted, (0, 0), converted)
    else:
        fresh.paste(converted, (0, 0))
    # Defensive: a fresh canvas has no info dict, and paste() never adds one.
    fresh.info.clear()
    return fresh


# Backwards-compatible private alias.
_strip_to_clean_image = _fresh_frame


def _removed_tag_names(analysis: dict[str, Any]) -> list[str]:
    """Real, human-readable names of everything that will be dropped."""
    names: list[str] = []
    exif = analysis.get("exif") or {}
    names.extend(str(k) for k in exif)
    gps = analysis.get("gps") or {}
    names.extend(str(k) for k in gps)
    for key in analysis.get("metadata") or {}:
        if str(key) in ("exif", "gps", "icc_profile"):
            continue
        names.append(str(key))
    # De-duplicate while preserving order, then sort for stable output.
    seen = set()
    ordered = []
    for n in names:
        if n not in seen:
            seen.add(n)
            ordered.append(n)
    return sorted(ordered)


def _removed_categories(analysis: dict[str, Any]) -> list[str]:
    cats = []
    for cat in ("exif", "gps", "icc_profile", "xmp", "comment"):
        if (analysis.get("details") or {}).get(cat):
            cats.append(cat)
    for key in analysis.get("metadata") or {}:
        if str(key) not in cats and str(key) not in ("exif", "gps"):
            cats.append(str(key))
    return cats


def _save_kwargs(save_format: str, quality: int) -> dict[str, Any]:
    if save_format == "JPEG":
        return {"format": "JPEG", "quality": quality, "optimize": True, "progressive": False}
    if save_format == "PNG":
        return {"format": "PNG", "optimize": True}
    if save_format == "WEBP":
        return {"format": "WEBP", "quality": quality, "method": 4}
    if save_format == "HEIF":  # pragma: no cover - optional
        return {"format": "HEIF", "quality": quality}
    raise ValueError(f"Unsupported save format: {save_format}")


def _flatten_for_jpeg(frame: Image.Image) -> Image.Image:
    if frame.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", frame.size, (255, 255, 255))
        alpha = frame.split()[-1]
        bg.paste(frame.convert("RGB"), (0, 0), alpha)
        bg.info.clear()
        return bg
    if frame.mode != "RGB":
        out = frame.convert("RGB")
        out.info.clear()
        return out
    return frame


def clean_metadata(
    input_path: str,
    output_path: str | None = None,
    resize: tuple[int, int] | None = None,
    watermark_text: str | None = None,
    quality: int = 95,
    *,
    auto_orient: bool = True,
    keep_icc: bool = False,
    opacity: float = 0.35,
    watermark_position: str = "bottom-right",
    overwrite: bool = False,
    verify: bool = True,
    preserve_animation: bool = True,
) -> dict[str, Any]:
    """Remove every metadata chunk from an image and save a clean copy.

    - Never modifies ``input_path``.
    - Creates parent directories for ``output_path``.
    - Output format is inferred from the output extension, else the source format.
    - ``auto_orient`` bakes the EXIF orientation into the pixels first, so
      portrait phone photos are not delivered sideways.
    - ``keep_icc`` keeps the colour profile (colour fidelity) instead of
      dropping it; the profile stays out of the "verified clean" check.
    - ``overwrite`` must be True to replace an existing output file otherwise
      FileExistsError is raised.
    """
    if not input_path or not isinstance(input_path, str):
        raise ValueError("input_path must be a non-empty string")
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"File not found: {input_path}")

    resize = _validate_resize(resize)
    quality = _validate_quality(quality)
    opacity = _validate_opacity(opacity)
    if watermark_text is not None:
        if not str(watermark_text).strip():
            raise ValueError("Watermark text must be non-empty")
        if len(str(watermark_text).strip()) > MAX_WATERMARK_LEN:
            raise ValueError(f"Watermark too long (max {MAX_WATERMARK_LEN} chars)")
        if str(watermark_position).lower() not in {
            "bottom-right",
            "bottom-left",
            "bottom-center",
            "top-right",
            "top-left",
            "top-center",
            "center",
        }:
            raise ValueError("invalid watermark position")

    analysis = analyze_metadata(input_path)
    if "error" in analysis:
        raise ValueError(f"Cannot read image: {analysis['error']}")

    src_format = _normalize_format(analysis.get("format"))
    if src_format not in SUPPORTED_FORMATS:
        supported = ", ".join(SUPPORTED_FORMATS)
        raise ValueError(
            f"Unsupported image format '{analysis.get('format')}'. Supported: {supported}"
            + ("" if _HEIF_AVAILABLE else " (install pillow-heif for HEIC/HEIF)")
        )

    # ---- resolve output path before any heavy work (fail fast) ----------
    if output_path is None:
        base, ext = os.path.splitext(input_path)
        if ext.lower() not in SUPPORTED_EXTENSIONS:
            ext = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "HEIF": ".heic"}.get(src_format or "", ".png")
        output_path = f"{base}_cleaned{ext}"
    else:
        if not isinstance(output_path, str) or not output_path.strip():
            raise ValueError("output_path must be a non-empty string")
        try:
            if os.path.abspath(output_path) == os.path.abspath(input_path):
                raise ValueError("output_path must differ from input_path (refusing to overwrite original)")
        except ValueError:
            raise
        except Exception:
            pass

    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(f"Output already exists: {output_path} (pass overwrite=True to replace)")

    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    save_format = format_for_extension(output_path, src_format)

    with Image.open(input_path) as img:
        img.load()

        # Explicit guard (Pillow's bomb check only warns by default for some paths).
        if img.size[0] * img.size[1] > MAX_PIXELS:
            raise ValueError(
                f"Image too large: {img.size[0]}x{img.size[1]} pixels (max ~{MAX_PIXELS // 1_000_000} megapixels)"
            )

        n_frames = int(getattr(img, "n_frames", 1) or 1)
        is_animated = bool(getattr(img, "is_animated", False)) and n_frames > 1
        if not preserve_animation:
            is_animated = False

        durations: list[Any] = []
        loop = 0
        if is_animated:
            for i in range(n_frames):
                try:
                    img.seek(i)
                    durations.append(img.info.get("duration", 100))
                except Exception:
                    break
            loop = img.info.get("loop", 0) or 0
            with contextlib.suppress(Exception):
                img.seek(0)

        icc_profile = img.info.get("icc_profile") if keep_icc else None

        auto_oriented = False
        source_img: Image.Image = img
        if auto_orient and not is_animated:
            # Bake the orientation into the pixels BEFORE the tag is dropped.
            try:
                transposed = ImageOps.exif_transpose(img)
            except Exception:
                transposed = None
            if transposed is not None and transposed is not img:
                exif_map: dict[Any, Any] = {}
                with contextlib.suppress(Exception):
                    exif_map = dict(img.getexif() or {})
                auto_oriented = bool(exif_map.get(0x0112)) or (transposed.size != img.size)
                transposed.info.pop("exif", None)
                source_img = transposed
                source_img.load()

        # ---- rebuild every frame on a fresh canvas ----------------------
        frames: list[Image.Image] = []
        if is_animated:
            for frame in ImageSequence.Iterator(source_img):
                frames.append(_fresh_frame(frame))
            with contextlib.suppress(Exception):
                source_img.seek(0)
        else:
            frames.append(_fresh_frame(source_img))
        if not frames:
            raise ValueError("Image contains no decodable frames")

        if resize:
            frames = [f.resize(_fit_within(f.size, resize), Image.Resampling.LANCZOS) for f in frames]

        watermarked = False
        if watermark_text:
            frames = [
                add_watermark(f, str(watermark_text), opacity=opacity, position=watermark_position) for f in frames
            ]
            for f in frames:
                f.info.clear()
            watermarked = True

        animated_out = len(frames) > 1 and save_format in ("WEBP", "PNG", "HEIF")
        if not animated_out and len(frames) > 1:
            # JPEG has no animation container: keep the first frame, say so.
            frames = frames[:1]

        if save_format == "JPEG":
            frames = [_flatten_for_jpeg(f) for f in frames]

        save_kwargs = _save_kwargs(save_format, quality)
        if icc_profile and save_format in ("JPEG", "PNG", "WEBP"):
            save_kwargs["icc_profile"] = icc_profile
        if animated_out:
            save_kwargs.update(
                save_all=True,
                append_images=frames[1:],
                duration=durations or [100],
                loop=loop,
            )

        # Explicitly never pass exif / dpi / xmp / comment.
        frames[0].save(output_path, **save_kwargs)
        for f in frames:
            with contextlib.suppress(Exception):
                f.close()

    removed = _removed_tag_names(analysis)
    if keep_icc and icc_profile:
        removed = [n for n in removed if n.lower() not in ("icc_profile", "iccprofile")]
    categories = _removed_categories(analysis)

    verified: dict[str, Any] = {}
    if verify:
        check = analyze_metadata(output_path)
        if "error" in check:
            verified = {"has_metadata": None, "remaining": [], "error": check["error"]}
        else:
            remaining = sorted(str(k) for k in (check.get("metadata") or {}))
            if keep_icc and icc_profile:
                remaining = [k for k in remaining if k.lower() not in ("icc_profile", "iccprofile")]
            verified = {
                "has_metadata": bool(remaining),
                "remaining": remaining,
                "has_gps": bool(check.get("has_gps")),
                "file_size": check.get("file_size"),
                "size": check.get("size"),
            }

    return {
        "input": input_path,
        "output": output_path,
        "status": "success",
        "format": save_format,
        "original_format": src_format,
        "original_metadata": analysis,
        "removed": removed,
        "removed_count": len(removed),
        "removed_categories": categories,
        "kept": ["icc_profile"] if (keep_icc and icc_profile) else [],
        "verified": verified,
        "resized": resize is not None,
        "watermarked": bool(watermarked if watermark_text else False),
        "auto_oriented": auto_oriented,
        "is_animated": animated_out,
        "frames": len(frames),
    }


def batch_clean(
    input_paths: list[str],
    output_dir: str | None = None,
    resize: tuple[int, int] | None = None,
    watermark_text: str | None = None,
    quality: int = 95,
    *,
    auto_orient: bool = True,
    keep_icc: bool = False,
    opacity: float = 0.35,
    watermark_position: str = "bottom-right",
    overwrite: bool = False,
    out_format: str | None = None,
    jobs: int = 1,
    skip_existing: bool = False,
    progress: Callable[[int, int, str], None] | None = None,
) -> list[dict[str, Any]]:
    """Process many files. Never raises — returns one status dict per file.

    ``out_format`` forces an output extension (e.g. ``png``) for every file.
    ``jobs`` > 1 uses a thread pool (Pillow releases the GIL while encoding).
    ``progress`` is called as ``progress(done, total, path)``.
    """
    if not input_paths:
        return []

    def _fail(msg: str) -> list[dict[str, Any]]:
        return [{"input": p, "status": "failed", "error": msg} for p in input_paths]

    try:
        _validate_resize(resize)
        _validate_quality(quality)
        _validate_opacity(opacity)
    except Exception as e:
        return _fail(str(e))

    forced_ext = None
    if out_format:
        forced_ext = "." + str(out_format).lstrip(".").lower()
        if forced_ext not in _EXT_TO_FORMAT:
            return _fail(f"Unsupported --format '{out_format}'. Supported: {', '.join(sorted(set(_EXT_TO_FORMAT)))}")

    if output_dir:
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            return _fail(f"Cannot create output_dir: {e}")

    total = len(input_paths)
    done = 0

    def _job(index_and_path: tuple[int, str]) -> dict[str, Any]:
        _index, path = index_and_path
        try:
            if output_dir:
                base, ext = os.path.splitext(os.path.basename(path))
                if forced_ext:
                    ext = forced_ext
                elif ext.lower() not in SUPPORTED_EXTENSIONS:
                    ext = ".jpg"
                out_path = os.path.join(output_dir, f"{base}_cleaned{ext}")
            else:
                out_path = None
            if skip_existing and out_path and os.path.exists(out_path):
                return {
                    "input": path,
                    "output": out_path,
                    "status": "skipped",
                    "reason": "output exists",
                }
            return clean_metadata(
                path,
                out_path,
                resize,
                watermark_text,
                quality,
                auto_orient=auto_orient,
                keep_icc=keep_icc,
                opacity=opacity,
                watermark_position=watermark_position,
                overwrite=overwrite,
            )
        except Exception as e:
            return {"input": path, "status": "failed", "error": f"{type(e).__name__}: {e}"}

    indexed = list(enumerate(input_paths))
    if jobs and jobs > 1:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results: list[dict[str, Any] | None] = [None] * total
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = {pool.submit(_job, item): item[0] for item in indexed}
            for fut in as_completed(futures):
                idx = futures[fut]
                results[idx] = fut.result()
                done += 1
                if progress:
                    progress(done, total, input_paths[idx])
        return [r for r in results if r is not None]

    out_list: list[dict[str, Any]] = []
    for item in indexed:
        result = _job(item)
        out_list.append(result)
        done += 1
        if progress:
            progress(done, total, item[1])
    return out_list

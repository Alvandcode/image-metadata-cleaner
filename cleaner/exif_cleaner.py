"""Image Metadata Cleaner — core library.

Privacy-first cleaning: rebuilds pixel data into a fresh image so no
EXIF / GPS / ICC / XMP / comment chunks survive. Never touches input file.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import piexif
from PIL import ExifTags, Image, ImageDraw, ImageFont

# Pillow security: block decompression-bomb DoS.
# Cap at ~50MP (below Pillow default ~178MP) to bound RAM/CPU on untrusted input.
# Resize targets are additionally validated in _validate_resize.
try:
    _default_max = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = min(_default_max or 50_000_000, 50_000_000)
except Exception:
    Image.MAX_IMAGE_PIXELS = 50_000_000
Image.LOAD_TRUNCATED_IMAGES = False

SUPPORTED_FORMATS = ("JPEG", "JPG", "PNG", "WEBP")
MAX_DIMENSION = 10000  # max width/height for --resize (DoS guard)
MAX_WATERMARK_LEN = 200

# Metadata keys stored in Pillow `info` that must be considered metadata.
_INFO_METADATA_KEYS = {
    "exif", "icc_profile", "iccprofile", "xmp", "xml:com.adobe.xmp",
    "comment", "dpi", "jfif", "jfif_version", "jfif_unit", "jfif_density",
    "adobe", "photoshop", "iptc", "interlace", "transparency",
}


def _resolve_tag_name(tag_id: int) -> str:
    """Resolve numeric EXIF tag id to human readable name."""
    return ExifTags.TAGS.get(tag_id, f"Unknown_{tag_id}")


def analyze_metadata(image_path: str) -> Dict:
    """Analyze and report metadata present in an image (read-only).

    Never modifies the file. Returns dict with has_metadata/details/format/size/mode.
    On failure returns {"error": ...}.
    """
    try:
        if not os.path.isfile(image_path):
            return {"error": f"File not found: {image_path}"}
        with Image.open(image_path) as img:
            img.load()  # force parsing so truncated files raise now
            info: Dict = {}

            # --- EXIF via public API (not _getexif) ---
            try:
                raw_exif = img.getexif()
            except Exception:
                raw_exif = None
            if raw_exif:
                exif_dict: Dict[str, str] = {}
                for tag_id, value in raw_exif.items():
                    try:
                        name = _resolve_tag_name(int(tag_id))
                    except Exception:
                        name = f"Unknown_{tag_id}"
                    try:
                        txt = str(value)
                    except Exception:
                        txt = "<unprintable>"
                    exif_dict[str(name)] = txt[:200]
                if exif_dict:
                    info["exif"] = exif_dict

            # --- Rich EXIF/GPS via piexif (read-only load) ---
            try:
                piexif_data = piexif.load(image_path)
                gps = piexif_data.get("GPS", {}) if isinstance(piexif_data, dict) else {}
                if gps:
                    gps_human: Dict[str, str] = {}
                    for k, v in gps.items():
                        from piexif import GPSIFD

                        name = next(
                            (n for n, c in vars(GPSIFD).items() if c == k and not n.startswith("_")),
                            f"GPS_{k}",
                        )
                        gps_human[str(name)] = str(v)[:200]
                    if gps_human:
                        info["gps"] = gps_human
            except Exception:
                pass  # piexif can't parse PNG/WebP etc. — not fatal

            # --- Other Pillow info chunks ---
            if img.info:
                for key, value in img.info.items():
                    kl = str(key).lower()
                    if kl in ("exif",):
                        continue  # already reported
                    try:
                        txt = str(value)
                    except Exception:
                        txt = "<unprintable>"
                    # Truncate long blobs (icc_profile can be KBs)
                    info[str(key)] = txt[:200]

            has_meta = bool(info.get("exif") or info.get("gps")) or any(
                str(k).lower() in _INFO_METADATA_KEYS for k in info.keys()
            )
            # Any remaining info entries are also metadata-ish; count them.
            if info and not has_meta:
                has_meta = True

            try:
                file_size = os.path.getsize(image_path)
            except OSError:
                file_size = None

            return {
                "has_metadata": has_meta,
                "details": info,
                "format": img.format,
                "size": tuple(img.size),
                "mode": img.mode,
                "file_size": file_size,
            }
    except FileNotFoundError:
        return {"error": f"File not found: {image_path}"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a usable font cross-platform, with graceful fallback."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        try:
            if os.path.isfile(path):
                return ImageFont.truetype(path, size)
        except Exception:
            continue
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except Exception:
        pass
    return ImageFont.load_default()


def add_watermark(img: Image.Image, text: str, opacity: float = 0.35) -> Image.Image:
    """Add a semi-transparent watermark at bottom-right.

    Font size scales with image size; safe for tiny images.
    """
    if not text or not text.strip():
        raise ValueError("Watermark text must be non-empty")
    text = text.strip()
    if len(text) > MAX_WATERMARK_LEN:
        raise ValueError(f"Watermark too long (max {MAX_WATERMARK_LEN} chars)")
    if not (0.0 < opacity <= 1.0):
        raise ValueError("Opacity must be in (0, 1]")

    w, h = img.size
    if w <= 0 or h <= 0:
        raise ValueError("Invalid image dimensions")

    # Scale font: ~5% of min dimension, clamped.
    font_size = max(12, min(w, h) // 20)
    # Shrink if text would overflow.
    font = _load_font(font_size)

    base = img.convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # If still too wide, shrink font iteratively.
    while tw > w - 20 and font_size > 10:
        font_size = max(10, font_size - 2)
        font = _load_font(font_size)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    margin = max(8, min(w, h) // 40)
    x = max(margin, w - tw - margin)
    y = max(margin, h - th - margin)

    alpha = int(255 * opacity)
    # Slight shadow for readability on bright backgrounds.
    draw.text((x + 1, y + 1), text, fill=(0, 0, 0, alpha), font=font)
    draw.text((x, y), text, fill=(255, 255, 255, alpha), font=font)

    return Image.alpha_composite(base, layer)


def _validate_resize(resize: Optional[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
    if resize is None:
        return None
    if not isinstance(resize, (tuple, list)) or len(resize) != 2:
        raise ValueError("resize must be a (width, height) tuple")
    try:
        rw, rh = int(resize[0]), int(resize[1])
    except Exception:
        raise ValueError("resize dimensions must be integers")
    if rw <= 0 or rh <= 0:
        raise ValueError("resize dimensions must be positive (e.g. 800x600)")
    if rw > MAX_DIMENSION or rh > MAX_DIMENSION:
        raise ValueError(f"resize dimensions too large (max {MAX_DIMENSION}x{MAX_DIMENSION})")
    if rw * rh > 50_000_000:
        raise ValueError("resize target too large (max ~50 megapixels)")
    return (rw, rh)


def _infer_save_format(output_path: str, fallback: Optional[str]) -> str:
    ext = os.path.splitext(output_path)[1].lower()
    mapping = {
        ".jpg": "JPEG",
        ".jpeg": "JPEG",
        ".png": "PNG",
        ".webp": "WEBP",
    }
    if ext in mapping:
        return mapping[ext]
    # No/unknown extension: fall back to source format if supported.
    if fallback in ("JPEG", "PNG", "WEBP"):
        return fallback
    raise ValueError(
        f"Unsupported output extension '{ext}'. Supported: .jpg .jpeg .png .webp"
    )


def _strip_to_clean_image(img: Image.Image) -> Image.Image:
    """Rebuild pixel data into a fresh image with zero metadata.

    Handles palette (P), grayscale+alpha (LA), RGBA, etc. safely.
    """
    # Normalize palette images first (preserves transparency if present).
    if img.mode == "P":
        transparency = img.info.get("transparency", None)
        if transparency is not None:
            clean = img.convert("RGBA")
        else:
            clean = img.convert("RGB")
    elif img.mode in ("LA", "La"):
        clean = img.convert("RGBA")
    elif img.mode in ("RGBA", "RGB", "L", "LA"):
        # Fresh canvas + paste keeps pixels, drops info dict.
        if img.mode == "RGBA":
            clean = Image.new("RGBA", img.size)
            clean.paste(img, (0, 0), img)
        elif img.mode == "LA":
            tmp = img.convert("RGBA")
            clean = Image.new("RGBA", img.size)
            clean.paste(tmp, (0, 0), tmp)
        else:
            clean = Image.new(img.mode, img.size)
            clean.paste(img, (0, 0))
    elif img.mode == "CMYK":
        clean = img.convert("RGB")
    else:
        # Fallback for exotic modes (I;16, F, etc.): go through RGB/RGBA.
        # SECURITY: never use img.copy() here — it preserves the info/metadata dict
        # and would leak EXIF/XMP into the "cleaned" file. Fail closed instead.
        try:
            converted = img.convert("RGB")
        except Exception:
            converted = None
            for _mode in ("RGBA", "L"):
                try:
                    converted = img.convert(_mode).convert("RGB")
                    break
                except Exception:
                    continue
            if converted is None:
                raise ValueError(f"Unsupported image mode {img.mode!r}: cannot strip safely")
        fresh = Image.new("RGB", img.size)
        fresh.paste(converted, (0, 0))
        clean = fresh
    # Defensive: ensure no metadata dict survives.
    try:
        clean.info.clear()
    except Exception:
        pass
    return clean


def clean_metadata(
    input_path: str,
    output_path: str | None = None,
    resize: Optional[Tuple[int, int]] = None,
    watermark_text: Optional[str] = None,
    quality: int = 95,
) -> Dict:
    """Remove all metadata from an image and save a clean copy.

    - Never modifies ``input_path``.
    - Creates parent directories for ``output_path``.
    - Output format is inferred from output extension; falls back to source.
    """
    if not input_path or not isinstance(input_path, str):
        raise ValueError("input_path must be a non-empty string")
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"File not found: {input_path}")

    resize = _validate_resize(resize)
    if watermark_text is not None and not str(watermark_text).strip():
        raise ValueError("Watermark text must be non-empty")
    if not isinstance(quality, int) or not (1 <= quality <= 100):
        raise ValueError("quality must be an integer in 1..100")

    analysis = analyze_metadata(input_path)
    if "error" in analysis:
        raise ValueError(f"Cannot read image: {analysis['error']}")

    # Resolve output path BEFORE heavy work so config errors fail fast.
    if output_path is None:
        base, ext = os.path.splitext(input_path)
        if ext.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            ext = ".jpg" if analysis.get("format") == "JPEG" else (".png" if analysis.get("format") == "PNG" else ".webp")
        output_path = f"{base}_cleaned{ext}"
    else:
        if not isinstance(output_path, str) or not output_path.strip():
            raise ValueError("output_path must be a non-empty string")
        # Refuse to overwrite the input file itself (symlink/hardlink aware).
        # abspath alone is bypassable via symlink -> use realpath + samefile.
        try:
            if os.path.realpath(output_path) == os.path.realpath(input_path):
                raise ValueError("output_path must differ from input_path (refusing to overwrite original)")
        except ValueError:
            raise
        except Exception:
            pass
        try:
            if os.path.lexists(output_path) and os.path.exists(input_path):
                if os.path.islink(output_path):
                    # Output symlink pointing at input (or anywhere sensitive): refuse.
                    # Caller should unlink/recreate instead of following it.
                    try:
                        if os.path.realpath(output_path) == os.path.realpath(input_path):
                            raise ValueError("output_path symlink resolves to input_path (refusing to follow)")
                    except ValueError:
                        raise
                    except Exception:
                        pass
                try:
                    if os.path.exists(output_path) and os.path.samefile(output_path, input_path):
                        raise ValueError("output_path is the same file as input_path (refusing to overwrite original)")
                except ValueError:
                    raise
                except OSError:
                    pass
        except ValueError:
            raise
        except Exception:
            pass

    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    src_format = analysis.get("format")
    save_format = _infer_save_format(output_path, src_format)

    with Image.open(input_path) as img:
        img.load()
        # Decompression-bomb guard is enforced by Pillow; surface a clear error.
        clean_img = _strip_to_clean_image(img)

        if resize:
            clean_img = clean_img.resize(resize, Image.Resampling.LANCZOS)
            try:
                clean_img.info.clear()
            except Exception:
                pass

        watermarked = False
        if watermark_text:
            clean_img = add_watermark(clean_img, watermark_text)
            watermarked = True

        # Flatten transparency for JPEG (white background, not black).
        if save_format == "JPEG" and clean_img.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", clean_img.size, (255, 255, 255))
            alpha = clean_img.split()[-1] if clean_img.mode == "RGBA" else clean_img.convert("RGBA").split()[-1]
            bg.paste(clean_img.convert("RGB"), (0, 0), alpha)
            clean_img = bg
        elif save_format == "JPEG" and clean_img.mode != "RGB":
            clean_img = clean_img.convert("RGB")

        save_kwargs: Dict = {}
        if save_format == "JPEG":
            save_kwargs = {"format": "JPEG", "quality": quality, "optimize": True, "progressive": False}
        elif save_format == "PNG":
            save_kwargs = {"format": "PNG", "optimize": True}
        elif save_format == "WEBP":
            save_kwargs = {"format": "WEBP", "quality": min(quality, 100), "method": 4}

        # Explicitly do NOT pass exif / icc_profile / dpi / xmp.
        clean_img.save(output_path, **save_kwargs)

    removed = list(analysis.get("details", {}).keys())
    return {
        "input": input_path,
        "output": output_path,
        "status": "success",
        "format": save_format,
        "original_metadata": analysis,
        "removed": removed,
        "removed_count": len(removed),
        "resized": resize is not None,
        "watermarked": watermarked if watermark_text else False,
    }


def batch_clean(
    input_paths: List[str],
    output_dir: str | None = None,
    resize: Optional[Tuple[int, int]] = None,
    watermark_text: Optional[str] = None,
    quality: int = 95,
) -> List[Dict]:
    """Process multiple files; never raises — per-file status dicts."""
    if not input_paths:
        return []
    # Validate resize/quality once so every file doesn't repeat the error.
    try:
        _validate_resize(resize)
    except Exception as e:
        return [{"input": p, "status": "failed", "error": str(e)} for p in input_paths]
    if output_dir:
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            return [{"input": p, "status": "failed", "error": f"Cannot create output_dir: {e}"} for p in input_paths]

    results: List[Dict] = []
    for path in input_paths:
        try:
            if output_dir:
                name = os.path.basename(path)
                base, ext = os.path.splitext(name)
                if ext.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                    ext = ".jpg"
                out_path = os.path.join(output_dir, f"{base}_cleaned{ext}")
            else:
                out_path = None
            results.append(clean_metadata(path, out_path, resize, watermark_text, quality))
        except Exception as e:
            results.append({"input": path, "status": "failed", "error": f"{type(e).__name__}: {e}"})
    return results

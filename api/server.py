"""Secure Flask API for image-metadata-cleaner.

Everything is streamed: the upload is written to a temp file in chunks, the
clean copy is streamed back from disk, and the temp directory is removed when
the response finishes. Nothing is buffered whole in RAM.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile

from flask import Flask, Response, jsonify, request, stream_with_context
from werkzeug.utils import secure_filename

try:
    from cleaner.exif_cleaner import (
        _HEIF_AVAILABLE,
        SUPPORTED_EXTENSIONS,
        SUPPORTED_FORMATS,
        analyze_metadata,
        clean_metadata,
    )
except ImportError:  # running from a different CWD: add repo root to path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from cleaner.exif_cleaner import (  # type: ignore
        _HEIF_AVAILABLE,
        SUPPORTED_EXTENSIONS,
        SUPPORTED_FORMATS,
        analyze_metadata,
        clean_metadata,
    )

from PIL import Image

API_VERSION = "0.3.0"
CHUNK_SIZE = 64 * 1024

app = Flask(__name__)

# 16 MB upload cap (DoS guard). Configurable via env.
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_UPLOAD_MB", "16")) * 1024 * 1024

ALLOWED_EXTENSIONS = set(SUPPORTED_EXTENSIONS)
_MIME_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "HEIF": "image/heic",
}


def _allowed(filename: str) -> bool:
    """Extension allow-list, applied to the client supplied filename."""
    return os.path.splitext(filename or "")[1].lower() in ALLOWED_EXTENSIONS


@app.after_request
def _security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.errorhandler(413)
def _too_large(_e):
    cap = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
    return jsonify({"error": f"File too large (max {cap}MB)"}), 413


@app.errorhandler(404)
def _not_found(_e):
    return jsonify({"error": "Not found"}), 404


@app.route("/", methods=["GET"])
def index():
    return jsonify(
        {
            "name": "image-metadata-cleaner",
            "version": API_VERSION,
            "privacy": "Uploads are processed in a temp file and deleted when the response ends.",
            "endpoints": {
                "POST /clean": "multipart field 'image' -> cleaned image download",
                "POST /analyze": "multipart field 'image' -> JSON metadata report",
                "GET /health": "liveness probe",
            },
            "clean_options": {
                "watermark": "text, drawn bottom-right",
                "opacity": "0-1, default 0.35",
                "resize": "WxH, e.g. 1200x800",
                "quality": "1-100, default 95",
                "format": "png | jpg | webp (force output format)",
                "keep_icc": "1 to keep the colour profile",
                "no_auto_orient": "1 to disable EXIF orientation baking",
            },
            "formats": sorted(SUPPORTED_FORMATS),
            "max_upload_mb": app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024),
        }
    )


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "version": API_VERSION}), 200


def _save_upload(upload, dest_dir: str) -> str:
    """Stream a validated upload to disk in chunks. Returns the temp path."""
    filename = secure_filename(upload.filename or "upload")
    if not _allowed(filename):
        raise ValueError(
            f"Unsupported file type '{os.path.splitext(filename)[1] or '?'}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}"
        )
    ext = os.path.splitext(filename)[1].lower()
    dest = os.path.join(dest_dir, f"input{ext}")
    written = 0
    with open(dest, "wb") as fh:
        stream = getattr(upload, "stream", None) or upload
        while True:
            chunk = stream.read(CHUNK_SIZE)
            if not chunk:
                break
            written += len(chunk)
            fh.write(chunk)
    if written == 0:
        raise ValueError("Empty file")
    return dest


def _validate_image(path: str) -> str:
    """Single-pass validation that the upload really is a decodable image."""
    try:
        with Image.open(path) as im:
            fmt = im.format
            im.load()
    except Exception:
        raise ValueError("File is not a valid image") from None
    if fmt == "MPO":  # multi-picture JPEG, still a JPEG
        fmt = "JPEG"
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported image format: {fmt}")
    return fmt


def _float_form(name: str, default: float) -> float:
    raw = request.form.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError as err:
        raise ValueError(f"'{name}' must be a number") from err


def _int_form(name: str, default: int) -> int:
    raw = request.form.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as err:
        raise ValueError(f"'{name}' must be an integer") from err


def _bool_form(name: str) -> bool:
    raw = (request.form.get(name) or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _parse_resize(raw: str | None) -> tuple[int, int] | None:
    if not raw:
        return None
    parts = str(raw).lower().replace("×", "x").replace("*", "x").split("x")
    if len(parts) != 2:
        raise ValueError("'resize' must look like 1200x800")
    try:
        return (int(parts[0]), int(parts[1]))
    except ValueError as err:
        raise ValueError("'resize' must look like 1200x800") from err


def _require_upload():
    """Shared preamble. Returns (upload, error_response)."""
    if "image" not in request.files:
        return None, (jsonify({"error": "No image provided (multipart field 'image' required)"}), 400)
    upload = request.files["image"]
    if not upload or not upload.filename:
        return None, (jsonify({"error": "No image provided"}), 400)
    return upload, None


def _file_chunks(path: str, cleanup_dir: str):
    """Stream a file in chunks, then delete the temp directory."""
    try:
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk
    finally:
        shutil.rmtree(cleanup_dir, ignore_errors=True)


@app.route("/clean", methods=["POST"])
def clean():
    upload, err = _require_upload()
    if err:
        return err

    work_dir = tempfile.mkdtemp(prefix="imc-")
    src_path = None
    try:
        try:
            src_path = _save_upload(upload, work_dir)
            _validate_image(src_path)
        except ValueError as e:
            shutil.rmtree(work_dir, ignore_errors=True)
            return jsonify({"error": str(e)}), 400

        safe_name = secure_filename(upload.filename or "image")
        base, ext = os.path.splitext(safe_name)
        if ext.lower() not in ALLOWED_EXTENSIONS:
            ext = os.path.splitext(src_path)[1]

        forced = (request.form.get("format") or "").strip().lstrip(".").lower()
        if forced:
            forced_ext = "." + forced
            if forced_ext not in ALLOWED_EXTENSIONS:
                shutil.rmtree(work_dir, ignore_errors=True)
                return jsonify({"error": f"Unsupported format '{forced}'"}), 400
            ext = forced_ext

        try:
            resize = _parse_resize(request.form.get("resize"))
            quality = _int_form("quality", 95)
            opacity = _float_form("opacity", 0.35)
        except ValueError as e:
            shutil.rmtree(work_dir, ignore_errors=True)
            return jsonify({"error": str(e)}), 400

        out_path = os.path.join(work_dir, f"output{ext.lower()}")

        try:
            result = clean_metadata(
                src_path,
                out_path,
                resize=resize,
                watermark_text=request.form.get("watermark") or None,
                quality=quality,
                auto_orient=not _bool_form("no_auto_orient"),
                keep_icc=_bool_form("keep_icc"),
                opacity=opacity,
                watermark_position=request.form.get("watermark_position") or "bottom-right",
            )
        except (ValueError, FileNotFoundError) as e:
            shutil.rmtree(work_dir, ignore_errors=True)
            return jsonify({"error": str(e)}), 400
        except Exception as e:  # pragma: no cover - unexpected
            app.logger.exception("clean failed")
            shutil.rmtree(work_dir, ignore_errors=True)
            return jsonify({"error": f"Processing failed: {type(e).__name__}"}), 500

        mimetype = _MIME_TYPES.get(result.get("format", "JPEG"), "application/octet-stream")
        download_name = f"cleaned_{base or 'image'}{ext}" if ext else f"cleaned_{base or 'image'}.jpg"
        resp = Response(
            stream_with_context(_file_chunks(result["output"], work_dir)),
            mimetype=mimetype,
        )
        resp.headers["Content-Disposition"] = f'attachment; filename="{download_name}"'
        resp.headers["X-Removed-Count"] = str(result.get("removed_count", 0))
        resp.headers["X-Verified-Clean"] = "1" if not (result.get("verified") or {}).get("has_metadata") else "0"
        resp.headers["X-Auto-Oriented"] = "1" if result.get("auto_oriented") else "0"
        resp.headers["X-Original-Format"] = str(result.get("original_format", ""))
        return resp
    except Exception:  # pragma: no cover - safety net
        shutil.rmtree(work_dir, ignore_errors=True)
        raise


@app.route("/analyze", methods=["POST"])
def analyze():
    upload, err = _require_upload()
    if err:
        return err

    work_dir = tempfile.mkdtemp(prefix="imc-")
    try:
        try:
            src_path = _save_upload(upload, work_dir)
            _validate_image(src_path)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        result = analyze_metadata(src_path)
        if "error" in result:
            return jsonify(result), 400
        return jsonify(result), 200
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def server_config() -> tuple[str, int, bool]:
    """Resolve (host, port, debug) from the environment.

    Host defaults to ``0.0.0.0``: binding ``127.0.0.1`` inside a container makes
    the published port unreachable from the host, which silently broke the
    documented ``docker run -p 5000:5000 ... python -m api.server`` workflow.
    Debug stays off unless FLASK_DEBUG=1 (it used to be a remote-code-execution
    vector).
    """
    host = os.environ.get("HOST") or "0.0.0.0"
    try:
        port = int(os.environ.get("PORT", "5000"))
    except ValueError:
        port = 5000
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    return host, port, debug


if __name__ == "__main__":
    host, port, debug = server_config()
    if not _HEIF_AVAILABLE:
        print("note: pillow-heif is not installed, HEIC/HEIF uploads will be rejected", file=sys.stderr)
    print(f"image-metadata-cleaner API {API_VERSION} -> http://{host}:{port}", file=sys.stderr)
    app.run(host=host, port=port, debug=debug, threaded=True)

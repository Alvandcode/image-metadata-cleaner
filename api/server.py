"""Secure Flask API for image-metadata-cleaner."""
from __future__ import annotations

import io
import os

from flask import Flask, jsonify, request, send_file
from werkzeug.utils import secure_filename

try:
    from cleaner.exif_cleaner import analyze_metadata, clean_metadata
except ImportError:  # running from a different CWD: add repo root to path
    import os as _os
    import sys as _sys

    _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from cleaner.exif_cleaner import analyze_metadata, clean_metadata  # type: ignore

import tempfile

from PIL import Image

app = Flask(__name__)

# 16 MB upload cap (DoS guard). Configurable via env.
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_UPLOAD_MB", "16")) * 1024 * 1024

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _allowed(filename: str) -> bool:
    return os.path.splitext(filename or "")[1].lower() in ALLOWED_EXTENSIONS


@app.after_request
def _security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


@app.errorhandler(413)
def _too_large(_e):
    return jsonify({"error": "File too large (max 16MB by default)"}), 413


@app.route("/", methods=["GET"])
def index():
    return jsonify(
        {
            "name": "image-metadata-cleaner",
            "version": "0.2.0",
            "endpoints": {
                "POST /clean": "multipart field 'image' -> cleaned image download",
                "POST /analyze": "multipart field 'image' -> JSON metadata report",
                "GET /health": "liveness probe",
            },
        }
    )


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


def _save_upload_to_temp(upload) -> str:
    """Validate upload is a real image, then persist to a temp file. Returns path."""
    filename = secure_filename(upload.filename or "upload")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}")
    data = upload.read()
    if not data:
        raise ValueError("Empty file")
    # Verify it's a real image (prevents polyglot / non-image DoS).
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            if im.format not in ("JPEG", "PNG", "WEBP"):
                raise ValueError(f"Unsupported image format: {im.format}")
    except ValueError:
        raise
    except Exception:
        raise ValueError("File is not a valid image")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    try:
        tmp.write(data)
        tmp.close()
    except Exception:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise
    return tmp.name


@app.route("/clean", methods=["POST"])
def clean():
    if "image" not in request.files:
        return jsonify({"error": "No image provided (multipart field 'image' required)"}), 400
    upload = request.files["image"]
    if not upload or not upload.filename:
        return jsonify({"error": "No image provided"}), 400

    src_path: str | None = None
    out_path: str | None = None
    try:
        try:
            src_path = _save_upload_to_temp(upload)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        safe_name = secure_filename(upload.filename or "image")
        base, ext = os.path.splitext(safe_name)
        if ext.lower() not in ALLOWED_EXTENSIONS:
            ext = os.path.splitext(src_path)[1]
        fd, out_path = tempfile.mkstemp(suffix=ext.lower())
        os.close(fd)

        try:
            result = clean_metadata(src_path, out_path)
        except (ValueError, FileNotFoundError) as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            app.logger.exception("clean failed")
            return jsonify({"error": f"Processing failed: {type(e).__name__}"}), 500

        # Stream bytes into memory, then delete temp files BEFORE responding
        # (avoids Windows file-lock race with send_file).
        with open(result["output"], "rb") as f:
            blob = f.read()
        mimetype = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(
            result.get("format", "JPEG"), "application/octet-stream"
        )
        return send_file(
            io.BytesIO(blob),
            as_attachment=True,
            download_name=f"cleaned_{base}{ext}",
            mimetype=mimetype,
        )
    finally:
        for p in (src_path, out_path):
            if p:
                try:
                    if os.path.exists(p):
                        os.unlink(p)
                except OSError:
                    pass


@app.route("/analyze", methods=["POST"])
def analyze():
    if "image" not in request.files:
        return jsonify({"error": "No image provided (multipart field 'image' required)"}), 400
    upload = request.files["image"]
    if not upload or not upload.filename:
        return jsonify({"error": "No image provided"}), 400

    src_path: str | None = None
    try:
        try:
            src_path = _save_upload_to_temp(upload)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        result = analyze_metadata(src_path)
        if "error" in result:
            return jsonify(result), 400
        return jsonify(result), 200
    finally:
        if src_path:
            try:
                if os.path.exists(src_path):
                    os.unlink(src_path)
            except OSError:
                pass


if __name__ == "__main__":
    # Never enable debug in production (was a critical RCE vector).
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    app.run(host=host, port=port, debug=debug)

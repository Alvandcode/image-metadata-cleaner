"""Regression tests for image-metadata-cleaner."""
import io
import os

import piexif
import pytest
from PIL import Image

from cleaner.exif_cleaner import analyze_metadata, batch_clean, clean_metadata
from cli.main import main as cli_main, parse_resize


@pytest.fixture()
def jpg_with_exif(tmp_path):
    p = tmp_path / "src.jpg"
    img = Image.new("RGB", (800, 600), color="red")
    zeroth = {
        piexif.ImageIFD.Make: "Canon",
        piexif.ImageIFD.Model: "EOS R5",
    }
    exif_d = {piexif.ExifIFD.DateTimeOriginal: "2024:01:01 10:00:00"}
    gps = {
        piexif.GPSIFD.GPSLatitudeRef: "N",
        piexif.GPSIFD.GPSLatitude: ((35, 1), (40, 1), (0, 1)),
        piexif.GPSIFD.GPSLongitudeRef: "E",
        piexif.GPSIFD.GPSLongitude: ((51, 1), (25, 1), (0, 1)),
    }
    exif_bytes = piexif.dump({"0th": zeroth, "Exif": exif_d, "GPS": gps, "Interop": {}, "1st": {}, "thumbnail": None})
    img.save(str(p), exif=exif_bytes)
    # snapshot input bytes to prove we never mutate input
    with open(p, "rb") as f:
        before = f.read()
    return p, before


def test_analyze_resolves_tag_names(jpg_with_exif):
    p, _ = jpg_with_exif
    r = analyze_metadata(str(p))
    assert "error" not in r
    assert r["has_metadata"] is True
    exif = r["details"].get("exif", {})
    # Must be human-readable, not Unknown_*
    assert "Model" in exif or "Make" in exif, exif
    assert not any(k.startswith("Unknown_271") for k in exif)


def test_clean_strips_exif_and_preserves_input(jpg_with_exif, tmp_path):
    p, before = jpg_with_exif
    out = tmp_path / "clean.jpg"
    res = clean_metadata(str(p), str(out))
    assert res["status"] == "success"
    assert os.path.isfile(out)
    # Input untouched
    with open(p, "rb") as f:
        assert f.read() == before
    # Output has no EXIF
    loaded = piexif.load(str(out))
    assert loaded["0th"] == {} and loaded["Exif"] == {} and loaded["GPS"] == {}
    with Image.open(out) as im:
        assert im.size == (800, 600)


def test_clean_png_and_webp(tmp_path):
    for ext, fmt in ((".png", "PNG"), (".webp", "WEBP")):
        src = tmp_path / f"a{ext}"
        Image.new("RGB", (100, 80), color="blue").save(str(src), format=fmt)
        out = tmp_path / f"a_clean{ext}"
        r = clean_metadata(str(src), str(out))
        assert r["status"] == "success"
        assert os.path.isfile(out)


def test_clean_palette_and_transparency(tmp_path):
    src = tmp_path / "p.png"
    Image.new("P", (64, 64)).save(str(src))
    r = clean_metadata(str(src), str(tmp_path / "p_clean.png"))
    assert r["status"] == "success"

    rgba = tmp_path / "t.png"
    Image.new("RGBA", (64, 64), (255, 0, 0, 128)).save(str(rgba))
    out = tmp_path / "t_clean.jpg"
    r2 = clean_metadata(str(rgba), str(out))
    assert r2["status"] == "success"
    with Image.open(out) as im:
        assert im.mode == "RGB"  # flattened for JPEG


def test_resize_validation(tmp_path):
    src = tmp_path / "s.jpg"
    Image.new("RGB", (50, 50), color="green").save(str(src))
    with pytest.raises((ValueError, Exception)):
        clean_metadata(str(src), str(tmp_path / "o.jpg"), resize=(0, 0))
    with pytest.raises((ValueError, Exception)):
        clean_metadata(str(src), str(tmp_path / "o.jpg"), resize=(-1, 10))
    clean_metadata(str(src), str(tmp_path / "o2.jpg"), resize=(25, 20))
    with Image.open(tmp_path / "o2.jpg") as im:
        assert im.size == (25, 20)


def test_watermark_small_image(tmp_path):
    src = tmp_path / "small.jpg"
    Image.new("RGB", (50, 50), color="green").save(str(src))
    out = tmp_path / "wm.jpg"
    r = clean_metadata(str(src), str(out), watermark_text="TEST")
    assert r["watermarked"] is True
    assert os.path.isfile(out)


def test_refuse_overwrite_input(jpg_with_exif):
    p, _ = jpg_with_exif
    with pytest.raises(ValueError):
        clean_metadata(str(p), str(p))


def test_batch(tmp_path, jpg_with_exif):
    p, _ = jpg_with_exif
    outdir = tmp_path / "out"
    res = batch_clean([str(p), str(tmp_path / "missing.jpg")], str(outdir))
    assert len(res) == 2
    assert res[0]["status"] == "success"
    assert res[1]["status"] == "failed"
    assert outdir.is_dir()


def test_cli_parse_resize():
    assert parse_resize("800x600") == (800, 600)
    assert parse_resize(" 800X600 ") == (800, 600)
    with pytest.raises(ValueError):
        parse_resize("bad")


def test_cli_no_match_returns_error(tmp_path, capsys):
    code = cli_main([str(tmp_path / "nope*.jpg")])
    assert code == 1


def test_cli_single_and_analyze(tmp_path, jpg_with_exif):
    p, _ = jpg_with_exif
    assert cli_main([str(p), "--analyze"]) == 0
    out = tmp_path / "cli_out.jpg"
    assert cli_main([str(p), "-o", str(out), "--overwrite"]) == 0
    assert out.is_file()


def test_api_clean_and_analyze(jpg_with_exif):
    from api.server import app

    p, _ = jpg_with_exif
    client = app.test_client()
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200

    with open(p, "rb") as f:
        data = {"image": (io.BytesIO(f.read()), "photo.jpg")}
        r = client.post("/clean", data=data, content_type="multipart/form-data")
    assert r.status_code == 200
    assert len(r.data) > 1000

    with open(p, "rb") as f:
        data = {"image": (io.BytesIO(f.read()), "photo.jpg")}
        r2 = client.post("/analyze", data=data, content_type="multipart/form-data")
    assert r2.status_code == 200
    assert r2.get_json()["has_metadata"] is True

    # Invalid image -> 400, not 500
    r3 = client.post(
        "/clean",
        data={"image": (io.BytesIO(b"not-an-image"), "x.jpg")},
        content_type="multipart/form-data",
    )
    assert r3.status_code == 400

    # Missing field -> 400
    assert client.post("/clean").status_code == 400

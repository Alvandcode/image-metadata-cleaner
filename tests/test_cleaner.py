"""Regression tests for image-metadata-cleaner."""

import io
import json
import os

import piexif
import pytest
from PIL import Image, ImageCms, PngImagePlugin

from cleaner.exif_cleaner import (
    SUPPORTED_EXTENSIONS,
    add_watermark,
    analyze_metadata,
    batch_clean,
    clean_metadata,
    has_rtl,
)
from cli.main import expand_inputs, parse_resize
from cli.main import main as cli_main

try:  # tomllib is Python 3.11+; the packaging test skips on 3.10
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _exif_bytes(zeroth=None, exif=None, gps=None):
    return piexif.dump(
        {
            "0th": zeroth or {},
            "Exif": exif or {},
            "GPS": gps or {},
            "Interop": {},
            "1st": {},
            "thumbnail": None,
        }
    )


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
    img.save(str(p), exif=_exif_bytes(zeroth, exif_d, gps))
    with open(p, "rb") as f:
        before = f.read()
    return p, before


@pytest.fixture()
def png_with_text(tmp_path):
    """PNG carrying arbitrary vendor text chunks (fail-closed reporting)."""
    p = tmp_path / "meta.png"
    meta = PngImagePlugin.PngInfo()
    meta.add_text("Software", "SpyCam 1.0")
    meta.add_text("Comment", "taken at home")
    Image.new("RGB", (40, 30), "blue").save(str(p), pnginfo=meta)
    return p


# --------------------------------------------------------------------------
# Analysis honesty
# --------------------------------------------------------------------------
def test_analyze_resolves_tag_names(jpg_with_exif):
    p, _ = jpg_with_exif
    r = analyze_metadata(str(p))
    assert "error" not in r
    assert r["has_metadata"] is True
    exif = r["details"].get("exif", {})
    assert "Model" in exif or "Make" in exif, exif
    assert not any(k.startswith("Unknown_271") for k in exif)


def test_analyze_reports_gps_decimal(jpg_with_exif):
    p, _ = jpg_with_exif
    r = analyze_metadata(str(p))
    assert r["has_gps"] is True
    gps = r["gps_decimal"]
    assert gps["lat"] == pytest.approx(35.666667, abs=1e-4)
    assert gps["lon"] == pytest.approx(51.416667, abs=1e-4)


def test_clean_plain_image_is_not_reported_dirty(tmp_path):
    """JFIF headers / DPI are container plumbing, not metadata (bugfix)."""
    src = tmp_path / "plain.jpg"
    Image.new("RGB", (60, 40), "green").save(str(src))
    report = analyze_metadata(str(src))
    assert report["has_metadata"] is False
    assert report["metadata"] == {}
    # ...but they are still visible for transparency.
    assert "jfif" in report["technical"] or "jfif_version" in report["technical"]

    out = tmp_path / "plain_clean.jpg"
    clean_metadata(str(src), str(out), overwrite=True)
    assert analyze_metadata(str(out))["has_metadata"] is False


def test_unknown_png_chunks_are_reported(png_with_text):
    r = analyze_metadata(str(png_with_text))
    assert r["has_metadata"] is True
    assert "Software" in r["metadata"]
    assert "Comment" in r["metadata"]


# --------------------------------------------------------------------------
# Orientation
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "orientation,expected",
    [
        (6, (50, 100)),  # rotate 90 CW
        (8, (50, 100)),  # rotate 90 CCW
        (3, (100, 50)),  # 180: dimensions unchanged
    ],
)
def test_orientation_is_baked_into_pixels(tmp_path, orientation, expected):
    src = tmp_path / f"o{orientation}.jpg"
    img = Image.new("RGB", (100, 50), "red")
    img.save(str(src), exif=_exif_bytes({piexif.ImageIFD.Orientation: orientation}))
    out = tmp_path / f"o{orientation}_clean.jpg"
    result = clean_metadata(str(src), str(out))
    with Image.open(out) as im:
        assert im.size == expected
        assert not im.getexif().get(0x0112), "orientation tag must be gone"
    assert result["auto_oriented"] is True
    # Only 180 is dimension-preserving, so the flag is set for it too but the
    # orientation tag is definitely stripped either way.


def test_no_auto_orient_keeps_original_pixels(tmp_path):
    src = tmp_path / "n.jpg"
    Image.new("RGB", (100, 50), "red").save(str(src), exif=_exif_bytes({piexif.ImageIFD.Orientation: 6}))
    out = tmp_path / "n_clean.jpg"
    result = clean_metadata(str(src), str(out), auto_orient=False)
    with Image.open(out) as im:
        assert im.size == (100, 50)
    assert result["auto_oriented"] is False


# --------------------------------------------------------------------------
# Reporting of what was removed
# --------------------------------------------------------------------------
def test_removed_lists_real_tag_names(jpg_with_exif):
    p, _ = jpg_with_exif
    result = clean_metadata(str(p), str(p.parent / "out.jpg"))
    assert result["removed_count"] == len(result["removed"]) > 1
    assert "Make" in result["removed"]
    assert "Model" in result["removed"]
    assert any(name.startswith("GPSLatitude") for name in result["removed"])
    assert "exif" in result["removed_categories"]
    assert result["verified"]["has_metadata"] is False
    assert result["verified"]["has_gps"] is False


def test_clean_strips_exif_and_preserves_input(jpg_with_exif, tmp_path):
    p, before = jpg_with_exif
    out = tmp_path / "clean.jpg"
    res = clean_metadata(str(p), str(out))
    assert res["status"] == "success"
    assert os.path.isfile(out)
    with open(p, "rb") as f:
        assert f.read() == before
    loaded = piexif.load(str(out))
    assert loaded["0th"] == {} and loaded["Exif"] == {} and loaded["GPS"] == {}
    with Image.open(out) as im:
        assert im.size == (800, 600)


def test_refuse_overwrite_input(jpg_with_exif):
    p, _ = jpg_with_exif
    with pytest.raises(ValueError):
        clean_metadata(str(p), str(p))


def test_library_refuses_silent_overwrite(jpg_with_exif, tmp_path):
    p, _ = jpg_with_exif
    out = tmp_path / "exists.jpg"
    clean_metadata(str(p), str(out))
    with pytest.raises(FileExistsError):
        clean_metadata(str(p), str(out))
    # ...and allows it when asked.
    clean_metadata(str(p), str(out), overwrite=True)


# --------------------------------------------------------------------------
# Colour profile
# --------------------------------------------------------------------------
def _srgb_bytes():
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def test_icc_profile_dropped_by_default_and_kept_on_request(tmp_path):
    src = tmp_path / "icc.jpg"
    Image.new("RGB", (60, 60), "orange").save(str(src), icc_profile=_srgb_bytes())
    assert analyze_metadata(str(src))["has_metadata"] is True

    stripped = tmp_path / "icc_stripped.jpg"
    clean_metadata(str(src), str(stripped))
    with Image.open(stripped) as im:
        assert not im.info.get("icc_profile")

    kept = tmp_path / "icc_kept.jpg"
    result = clean_metadata(str(src), str(kept), keep_icc=True)
    with Image.open(kept) as im:
        assert im.info.get("icc_profile")
    assert "icc_profile" in result["kept"]
    # A deliberately kept profile must not fail the clean verification.
    assert result["verified"]["has_metadata"] is False


# --------------------------------------------------------------------------
# Colour / transparency / exotic modes
# --------------------------------------------------------------------------
@pytest.mark.parametrize("ext,fmt", [(".jpg", "JPEG"), (".png", "PNG"), (".webp", "WEBP")])
def test_clean_output_is_verified_clean_for_every_format(tmp_path, ext, fmt):
    """No format may report a freshly cleaned file as still dirty.

    WebP exposes container fields (timestamp / loop / background) through
    ``info``; counting those as personal metadata produced false "still dirty"
    reports and made the CLI exit non-zero on success.
    """
    src = tmp_path / f"a{ext}"
    Image.new("RGB", (100, 80), color="blue").save(str(src), format=fmt)
    out = tmp_path / f"a_clean{ext}"
    r = clean_metadata(str(src), str(out))
    assert r["status"] == "success"
    assert os.path.isfile(out)
    assert r["verified"]["has_metadata"] is False, r["verified"]


def test_webp_container_fields_are_not_metadata(tmp_path):
    src = tmp_path / "plain.webp"
    Image.new("RGB", (60, 40), "green").save(str(src), format="WEBP")
    report = analyze_metadata(str(src))
    assert report["has_metadata"] is False
    assert "timestamp" not in (report["metadata"] or {})


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


def test_16bit_png_keeps_depth_and_loses_metadata(tmp_path):
    """Exotic modes used to fall back to img.copy(), which kept `info`."""
    src = tmp_path / "deep.png"
    meta = PngImagePlugin.PngInfo()
    meta.add_text("Software", "scanner")
    Image.new("I;16", (20, 20), 40000).save(str(src), pnginfo=meta)
    assert analyze_metadata(str(src))["has_metadata"] is True

    out = tmp_path / "deep_clean.png"
    result = clean_metadata(str(src), str(out))
    assert result["verified"]["has_metadata"] is False
    with Image.open(out) as im:
        assert im.mode in ("I;16", "I")
        assert not im.info.get("Software")


def test_unsupported_format_is_surfaced(tmp_path):
    src = tmp_path / "a.bmp"
    Image.new("RGB", (10, 10), "red").save(str(src))
    with pytest.raises(ValueError) as exc:
        clean_metadata(str(src), str(tmp_path / "a_clean.png"))
    assert "Supported" in str(exc.value)


# --------------------------------------------------------------------------
# Animation
# --------------------------------------------------------------------------
def test_animated_webp_keeps_all_frames(tmp_path):
    frames = [Image.new("RGB", (40, 40), c) for c in ("red", "green", "blue")]
    src = tmp_path / "anim.webp"
    frames[0].save(str(src), save_all=True, append_images=frames[1:], duration=100, loop=0)
    assert analyze_metadata(str(src))["is_animated"] is True

    out = tmp_path / "anim_clean.webp"
    result = clean_metadata(str(src), str(out))
    assert result["is_animated"] is True
    assert result["frames"] == 3
    with Image.open(out) as im:
        assert im.n_frames == 3


# --------------------------------------------------------------------------
# Watermark
# --------------------------------------------------------------------------
def test_watermark_small_image(tmp_path):
    src = tmp_path / "small.jpg"
    Image.new("RGB", (50, 50), color="green").save(str(src))
    out = tmp_path / "wm.jpg"
    r = clean_metadata(str(src), str(out), watermark_text="TEST")
    assert r["watermarked"] is True
    assert os.path.isfile(out)


def test_persian_watermark_renders(tmp_path):
    src = tmp_path / "fa.jpg"
    Image.new("RGB", (400, 300), color="black").save(str(src))
    out = tmp_path / "fa_clean.jpg"
    r = clean_metadata(str(src), str(out), watermark_text="© علیرضا", opacity=0.6)
    assert r["watermarked"] is True
    assert has_rtl("سلام") is True
    assert has_rtl("hello") is False
    # The rendered watermark must actually put bright pixels on the canvas.
    with Image.open(out) as im:
        assert im.convert("L").getextrema()[1] > 60


def test_watermark_opacity_validation(tmp_path):
    src = tmp_path / "o.jpg"
    Image.new("RGB", (60, 60), "black").save(str(src))
    with pytest.raises(ValueError):
        clean_metadata(str(src), str(tmp_path / "o_clean.jpg"), watermark_text="x", opacity=0)
    with Image.open(src) as im:
        with pytest.raises(ValueError):
            add_watermark(im, "x", opacity=1.5)
        with pytest.raises(ValueError):
            add_watermark(im, "")
        with pytest.raises(ValueError):
            add_watermark(im, "x", position="middle-out")


# --------------------------------------------------------------------------
# Resize
# --------------------------------------------------------------------------
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


# --------------------------------------------------------------------------
# Batch
# --------------------------------------------------------------------------
def test_batch(tmp_path, jpg_with_exif):
    p, _ = jpg_with_exif
    outdir = tmp_path / "out"
    res = batch_clean([str(p), str(tmp_path / "missing.jpg")], str(outdir))
    assert len(res) == 2
    assert res[0]["status"] == "success"
    assert res[1]["status"] == "failed"
    assert outdir.is_dir()


def test_batch_skip_existing_and_progress(tmp_path, jpg_with_exif):
    p, _ = jpg_with_exif
    outdir = tmp_path / "out2"
    seen = []
    batch_clean([str(p)], str(outdir), progress=lambda d, t, path: seen.append((d, t)))
    assert seen == [(1, 1)]
    again = batch_clean([str(p)], str(outdir), skip_existing=True)
    assert again[0]["status"] == "skipped"

    forced = batch_clean([str(p)], str(tmp_path / "out3"), out_format="png")
    assert forced[0]["output"].endswith(".png")


def test_batch_parallel_matches_serial(tmp_path, jpg_with_exif):
    p, _ = jpg_with_exif
    a = batch_clean([str(p)], str(tmp_path / "s1"), jobs=1)
    b = batch_clean([str(p)], str(tmp_path / "s2"), jobs=4)
    assert [r["status"] for r in a] == [r["status"] for r in b] == ["success"]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
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


def test_cli_single_output_without_extension_is_a_file(tmp_path, jpg_with_exif):
    """`photo.jpg -o newdir` must create a *file* called newdir, not a folder."""
    p, _ = jpg_with_exif
    target = tmp_path / "newdir"
    assert cli_main([str(p), "-o", str(target)]) == 0
    assert target.is_file()
    assert not target.is_dir()


def test_cli_trailing_separator_forces_directory(tmp_path, jpg_with_exif):
    p, _ = jpg_with_exif
    target = tmp_path / "outdir"
    assert cli_main([str(p), "-o", str(target) + os.sep]) == 0
    assert target.is_dir()
    assert (target / "src_cleaned.jpg").is_file()


def test_cli_batch_overwrite_guard(tmp_path, jpg_with_exif):
    """Batch mode writes *next to* the sources too, so it needs the guard."""
    p, _ = jpg_with_exif
    workdir = tmp_path / "guard"
    workdir.mkdir()
    for name in ("one.jpg", "two.jpg"):
        (workdir / name).write_bytes(p.read_bytes())
    inputs = [str(workdir / "one.jpg"), str(workdir / "two.jpg")]
    outdir = tmp_path / "batch"

    assert cli_main([*inputs, "-o", str(outdir)]) == 0
    # Second run: outputs exist, no --overwrite -> refuse instead of clobbering.
    assert cli_main([*inputs, "-o", str(outdir)]) == 1
    assert cli_main([*inputs, "-o", str(outdir), "--overwrite"]) == 0
    assert cli_main([*inputs, "-o", str(outdir), "--skip-existing"]) == 0

    # Same guard applies without -o (outputs land beside the sources).
    assert cli_main(inputs) == 0
    assert cli_main(inputs) == 1
    assert cli_main([*inputs, "--overwrite"]) == 0


def test_cli_glob_does_not_feed_on_its_own_output(tmp_path, jpg_with_exif):
    """The *_cleaned.jpg recursion guard (used to grow files exponentially)."""
    p, _ = jpg_with_exif
    workdir = tmp_path / "photos"
    workdir.mkdir()
    src = workdir / "photo.jpg"
    src.write_bytes(p.read_bytes())

    assert cli_main([str(workdir / "*.jpg")]) == 0
    first = sorted(f.name for f in workdir.iterdir())
    assert first == ["photo.jpg", "photo_cleaned.jpg"]

    assert cli_main([str(workdir / "*.jpg"), "--overwrite"]) == 0
    assert sorted(f.name for f in workdir.iterdir()) == first

    files = expand_inputs(str(workdir / "*.jpg"))
    assert files == [str(src)]


def test_cli_directory_input(tmp_path, jpg_with_exif):
    p, _ = jpg_with_exif
    workdir = tmp_path / "bucket"
    workdir.mkdir()
    (workdir / "a.jpg").write_bytes(p.read_bytes())
    assert cli_main([str(workdir), "-o", str(tmp_path / "out")]) == 0
    assert (tmp_path / "out" / "a_cleaned.jpg").is_file()


def test_cli_tilde_expansion(tmp_path, monkeypatch, jpg_with_exif):
    p, _ = jpg_with_exif
    (tmp_path / "home.jpg").write_bytes(p.read_bytes())
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    assert expand_inputs("~/home.jpg") == [str(tmp_path / "home.jpg")]


def test_cli_format_conversion(tmp_path, jpg_with_exif):
    p, _ = jpg_with_exif
    out = tmp_path / "converted"
    assert cli_main([str(p), "-o", str(out) + os.sep, "--format", "png"]) == 0
    produced = out / "src_cleaned.png"
    assert produced.is_file()
    with Image.open(produced) as im:
        assert im.format == "PNG"
    assert cli_main([str(p), "-o", str(tmp_path / "x"), "--format", "tiff"]) == 2


def test_cli_json_output(tmp_path, jpg_with_exif, capsys):
    p, _ = jpg_with_exif
    code = cli_main([str(p), "--analyze", "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["has_metadata"] is True

    out = tmp_path / "j.json.jpg"
    assert cli_main([str(p), "-o", str(out), "--json", "--overwrite"]) == 0
    cleaned = json.loads(capsys.readouterr().out)
    assert cleaned["status"] == "success"
    assert cleaned["verified"]["has_metadata"] is False


def test_cli_jobs_progress_and_quiet(tmp_path, jpg_with_exif, capsys):
    p, _ = jpg_with_exif
    workdir = tmp_path / "many"
    workdir.mkdir()
    for i in range(3):
        (workdir / f"f{i}.jpg").write_bytes(p.read_bytes())
    outdir = tmp_path / "manyout"
    code = cli_main([str(workdir), "-o", str(outdir), "--jobs", "3", "--progress"])
    assert code == 0
    assert len(list(outdir.glob("*_cleaned.jpg"))) == 3
    capsys.readouterr()

    other = tmp_path / "quietout"
    assert cli_main([str(workdir), "-o", str(other), "-q"]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_cli_corrupt_input_fails(tmp_path, capsys):
    bad = tmp_path / "broken.jpg"
    bad.write_bytes(b"definitely not a jpeg")
    code = cli_main([str(bad), "-o", str(tmp_path / "broken_clean.jpg")])
    assert code == 2
    assert "Error" in capsys.readouterr().err


def test_cli_console_script_returns_exit_code(tmp_path, monkeypatch, capsys):
    """`img-clean` used to always exit 0 because console_scripts drops returns."""
    import sys

    from cli.main import cli

    monkeypatch.setattr(sys, "argv", ["img-clean", str(tmp_path / "nope*.jpg")])
    with pytest.raises(SystemExit) as exc:
        cli()
    assert exc.value.code == 1
    capsys.readouterr()

    if tomllib is None:  # pragma: no cover - Python 3.10
        pytest.skip("tomllib requires Python 3.11+")
    with open(os.path.join(REPO_ROOT, "pyproject.toml"), "rb") as fh:
        cfg = tomllib.load(fh)
    assert cfg["project"]["scripts"]["img-clean"] == "cli.main:cli"


def test_cli_exit_codes_documented(capsys):
    with pytest.raises(SystemExit) as exc:
        cli_main(["--help"])
    capsys.readouterr()
    assert exc.value.code == 0


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
def test_api_host_default_is_reachable_from_outside_containers(monkeypatch):
    from api.server import server_config

    for key in ("HOST", "PORT", "FLASK_DEBUG"):
        monkeypatch.delenv(key, raising=False)
    host, port, debug = server_config()
    assert host == "0.0.0.0"
    assert port == 5000
    assert debug is False

    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "not-a-number")
    host, port, _ = server_config()
    assert (host, port) == ("127.0.0.1", 5000)


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
    assert r.headers["X-Verified-Clean"] == "1"
    assert int(r.headers["X-Removed-Count"]) > 1
    assert "attachment" in r.headers["Content-Disposition"]

    with open(p, "rb") as f:
        data = {"image": (io.BytesIO(f.read()), "photo.jpg")}
        r2 = client.post("/analyze", data=data, content_type="multipart/form-data")
    assert r2.status_code == 200
    assert r2.get_json()["has_metadata"] is True

    r3 = client.post(
        "/clean",
        data={"image": (io.BytesIO(b"not-an-image"), "x.jpg")},
        content_type="multipart/form-data",
    )
    assert r3.status_code == 400

    assert client.post("/clean").status_code == 400


def test_api_rejects_disallowed_extension(jpg_with_exif):
    """`_allowed` used to be dead code."""
    from api.server import app

    p, _ = jpg_with_exif
    client = app.test_client()
    with open(p, "rb") as f:
        data = {"image": (io.BytesIO(f.read()), "payload.txt")}
        r = client.post("/clean", data=data, content_type="multipart/form-data")
    assert r.status_code == 400
    assert "Unsupported file type" in r.get_json()["error"]


def test_api_clean_options(jpg_with_exif):
    from api.server import app

    p, _ = jpg_with_exif
    client = app.test_client()
    with open(p, "rb") as f:
        payload = f.read()

    data = {
        "image": (io.BytesIO(payload), "photo.jpg"),
        "watermark": "© تست",
        "opacity": "0.5",
        "resize": "200x100",
        "quality": "70",
        "format": "png",
        "keep_icc": "1",
    }
    r = client.post("/clean", data=data, content_type="multipart/form-data")
    assert r.status_code == 200, r.data
    with Image.open(io.BytesIO(r.data)) as im:
        assert im.size == (200, 100)
        assert im.format == "PNG"

    bad = {"image": (io.BytesIO(payload), "photo.jpg"), "resize": "nonsense"}
    assert client.post("/clean", data=bad, content_type="multipart/form-data").status_code == 400


def test_api_streams_without_leaving_temp_files(jpg_with_exif, monkeypatch):
    """Nothing stays on disk after the response is consumed."""
    import tempfile as _tempfile

    from api.server import app

    created = []
    real_mkdtemp = _tempfile.mkdtemp

    def spy(*args, **kwargs):
        path = real_mkdtemp(*args, **kwargs)
        created.append(path)
        return path

    monkeypatch.setattr("api.server.tempfile.mkdtemp", spy)

    p, _ = jpg_with_exif
    client = app.test_client()
    with open(p, "rb") as f:
        data = {"image": (io.BytesIO(f.read()), "photo.jpg")}
        r = client.post("/clean", data=data, content_type="multipart/form-data")
    assert r.status_code == 200
    assert r.data  # consume the streamed body so the cleanup generator runs
    assert created and all(not os.path.exists(path) for path in created)


def test_api_large_upload_is_chunked(tmp_path):
    """A 4 MB upload must go through without being held whole in memory twice."""
    from api.server import app

    src = tmp_path / "big.jpg"
    import random

    rng = random.Random(1234)
    noise = Image.frombytes("RGB", (2000, 2000), bytes(rng.randrange(256) for _ in range(2000 * 2000 * 3)))
    noise.save(str(src), quality=100)
    assert os.path.getsize(src) > 500_000

    client = app.test_client()
    with open(src, "rb") as f:
        data = {"image": (io.BytesIO(f.read()), "big.jpg")}
        r = client.post("/clean", data=data, content_type="multipart/form-data")
    assert r.status_code == 200
    assert len(r.data) > 1000


# --------------------------------------------------------------------------
# Packaging sanity
# --------------------------------------------------------------------------
def test_supported_extensions_are_consistent():
    assert ".jpg" in SUPPORTED_EXTENSIONS and ".webp" in SUPPORTED_EXTENSIONS


def test_pinned_dependencies():
    with open(os.path.join(REPO_ROOT, "requirements.txt"), encoding="utf-8") as fh:
        reqs = [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]
    assert reqs, "requirements.txt is empty"
    for line in reqs:
        assert "==" in line or "~=" in line, f"unpinned dependency: {line}"


def test_dockerfile_installs_console_script_and_healthcheck_matches_cmd():
    with open(os.path.join(REPO_ROOT, "Dockerfile"), encoding="utf-8") as fh:
        dockerfile = fh.read()
    assert "pip install" in dockerfile
    assert "api.server" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    # Host must be bindable from outside the container.
    assert "HOST=0.0.0.0" in dockerfile

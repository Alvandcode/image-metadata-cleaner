"""Property-based tests for the two promises this project makes.

The example-based suite in ``test_cleaner.py`` checks specific files. These
tests instead state the guarantees as invariants and let Hypothesis hunt for a
counter-example:

1. whatever a photo carried, the cleaned copy carries none of it;
2. the input file is byte-for-byte untouched.

Plus the EXIF orientation matrix, which silently broke every portrait photo
before 0.3.0 and is easy to break again.
"""

from __future__ import annotations

import hashlib
import pathlib

import piexif
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from PIL import Image, PngImagePlugin

from cleaner import analyze_metadata, clean_metadata

# Orientation 5-8 swap the axes, so they are the ones that catch a missing
# exif_transpose(). A non-square source makes the swap detectable.
PROPERTY_SETTINGS = settings(
    max_examples=10,
    deadline=None,
    # tmp_path is not reset between generated inputs on purpose: every example
    # overwrites the same two filenames, so nothing leaks from one to the next.
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)

SOURCE = (12, 7)
ORIENTED = {
    1: SOURCE,
    2: SOURCE,
    3: SOURCE,
    4: SOURCE,
    5: SOURCE[::-1],
    6: SOURCE[::-1],
    7: SOURCE[::-1],
    8: SOURCE[::-1],
}


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("orientation", sorted(ORIENTED))
def test_every_orientation_is_baked_into_the_pixels(tmp_path, orientation):
    src = tmp_path / "portrait.jpg"
    Image.new("RGB", SOURCE, "red").save(
        src, "JPEG", exif=piexif.dump({"0th": {piexif.ImageIFD.Orientation: orientation}})
    )

    out = tmp_path / f"portrait_{orientation}.jpg"
    result = clean_metadata(str(src), str(out))

    assert result["status"] == "success"
    with Image.open(out) as cleaned:
        assert cleaned.size == ORIENTED[orientation], f"orientation {orientation} was not applied"
    assert analyze_metadata(str(out))["has_metadata"] is False


@given(
    width=st.integers(min_value=3, max_value=40),
    height=st.integers(min_value=3, max_value=40),
    latitude=st.floats(min_value=-89.9, max_value=89.9, allow_nan=False, allow_infinity=False),
    longitude=st.floats(min_value=-179.9, max_value=179.9, allow_nan=False, allow_infinity=False),
    artist=st.text(alphabet="abcdefghijklmnopqrstuvwxyz 123", min_size=1, max_size=15),
)
@PROPERTY_SETTINGS
def test_no_jpeg_metadata_survives_cleaning(tmp_path, width, height, latitude, longitude, artist):
    src = tmp_path / "rand.jpg"
    Image.new("RGB", (width, height), "teal").save(src, "JPEG", quality=90)
    piexif.insert(
        piexif.dump(
            {
                "0th": {piexif.ImageIFD.Artist: artist},
                "GPS": {
                    piexif.GPSIFD.GPSLatitudeRef: b"N" if latitude >= 0 else b"S",
                    piexif.GPSIFD.GPSLatitude: ((abs(int(latitude)), 1), (0, 1), (0, 1)),
                    piexif.GPSIFD.GPSLongitudeRef: b"E" if longitude >= 0 else b"W",
                    piexif.GPSIFD.GPSLongitude: ((abs(int(longitude)), 1), (0, 1), (0, 1)),
                },
            }
        ),
        str(src),
    )

    before = sha256(src)
    out = tmp_path / "rand_clean.jpg"
    # overwrite=True: the examples share tmp_path, and the refusal-to-overwrite
    # guard has its own dedicated test.
    clean_metadata(str(src), str(out), overwrite=True)

    analysis = analyze_metadata(str(out))
    assert analysis["has_metadata"] is False, f"metadata survived: {analysis['details']}"
    assert analysis["has_gps"] is False, "GPS coordinates survived cleaning"
    assert analysis["gps_decimal"] == {}, "decimal GPS survived cleaning"
    assert sha256(src) == before, "the input file was modified"


@given(
    width=st.integers(min_value=3, max_value=40),
    height=st.integers(min_value=3, max_value=40),
    note=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=1, max_size=20),
)
@PROPERTY_SETTINGS
def test_no_png_text_chunks_survive_cleaning(tmp_path, width, height, note):
    src = tmp_path / "rand.png"
    info = PngImagePlugin.PngInfo()
    info.add_text("Comment", note)
    info.add_text("Author", "someone")
    Image.new("RGBA", (width, height), (10, 20, 30, 128)).save(src, "PNG", pnginfo=info)

    before = sha256(src)
    out = tmp_path / "rand_clean.png"
    clean_metadata(str(src), str(out), overwrite=True)

    assert analyze_metadata(str(out))["has_metadata"] is False
    assert sha256(src) == before


@given(
    width=st.integers(min_value=20, max_value=200),
    height=st.integers(min_value=20, max_value=200),
    max_dim=st.integers(min_value=8, max_value=120),
)
@PROPERTY_SETTINGS
def test_resize_never_exceeds_the_cap_and_keeps_the_ratio(tmp_path, width, height, max_dim):
    src = tmp_path / "big.png"
    Image.new("RGB", (width, height), "navy").save(src, "PNG")
    out = tmp_path / "big_clean.png"

    clean_metadata(str(src), str(out), resize=(max_dim, max_dim), overwrite=True)

    with Image.open(out) as cleaned:
        long_edge = max(width, height)
        if long_edge <= max_dim:
            assert cleaned.size == (width, height), "a photo inside the cap must not be touched"
        else:
            assert abs(max(cleaned.size) - max_dim) <= 1, "the long edge must reach the cap exactly"
            assert cleaned.size[0] <= width and cleaned.size[1] <= height, "resizing must never enlarge"
            # Aspect ratio survives, to within the one pixel that rounding costs.
            assert abs(cleaned.size[0] * height - cleaned.size[1] * width) <= max(width, height), (
                f"aspect ratio drifted: {cleaned.size} from {(width, height)}"
            )


@given(quality=st.integers(min_value=-500, max_value=500).filter(lambda v: not 1 <= v <= 100))
@PROPERTY_SETTINGS
def test_out_of_range_quality_is_rejected(tmp_path, quality):
    src = tmp_path / "q.png"
    Image.new("RGB", (8, 8), "black").save(src, "PNG")
    with pytest.raises((ValueError, TypeError)):
        clean_metadata(str(src), str(tmp_path / "q_clean.png"), quality=quality)

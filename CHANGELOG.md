# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/); versions
follow [SemVer](https://semver.org/).

## [0.4.0] — 2026-09-16

A hardening release: the distribution pipeline is now verifiable end to end, the
web app installs properly on iOS/Android, and two photo-corrupting bugs are gone.

### Fixed

- **`--resize` is now a bounding box.** It used to resize to an exact `WxH`, which
  squashed the aspect ratio, and it *enlarged* photos smaller than the box — both
  degraded images while claiming to tidy them. It now fits inside the box, keeps
  the ratio and never enlarges. `resize=(w, h)` in the Python API is unchanged.
- **The version was hard-coded in three places** (`cli/main.py`, `api/server.py`,
  `pyproject.toml`) and the CLI reported `0.3.0` while the wheel said `0.4.0`. The
  version now lives only in `cleaner/__init__.py`; `pyproject.toml` reads it.
- **The web app never corrupts oversized photos.** Browsers silently clamp a
  canvas that is too large, and a clamped width makes `drawImage()` crop instead
  of scale. The app now verifies the canvas it actually got, backs off and retries,
  and tells you when a photo had to be scaled down. It also reads the dimensions
  from the file header before decoding, so a too-large photo gets an accurate
  message instead of "not an image".
- iOS showed a blank home-screen icon: `apple-touch-icon` pointed at an SVG, which
  Safari ignores. There are real PNG icons now.

### Added

- **PyPI publishing** on `v*` tags via trusted publishing (OIDC, no stored
  token), with PEP 740 attestations, plus a guard that fails the release if the
  tag and the packaged version disagree.
- **Signed, verifiable releases:** build provenance attestations for the wheel,
  sdist and every PyInstaller binary, an SPDX SBOM for the whole release, and a
  `SHA256SUMS.txt` a downloader can check.
- **Container images on GHCR** with provenance and SBOM attestations.
- **`THREAT_MODEL.md`** — adversaries, trust boundaries, and an honest list of
  what cleaning does *not* guarantee.
- **CI security job:** `zizmor` audits the workflows themselves and `pip-audit`
  checks the pinned dependencies; pull requests get a dependency review. Every
  action is pinned by commit SHA, and checkouts no longer persist credentials.
- **Property-based tests** (`tests/test_properties.py`): the full 8-orientation
  EXIF matrix, "no metadata survives" over generated JPEG/PNG inputs, "the input
  file is byte-identical afterwards", and aspect-ratio/cap invariants for resize.
  The suite is 66 tests and CI enforces a coverage floor.
- **Mobile share target:** share a photo from any app's share sheet and it opens
  in the cleaner, straight into the drop zone.
- **Installable on mobile:** PNG + maskable icons, install-prompt screenshots, and
  a service-worker cache version stamped with the commit id on every deploy, so
  the app actually updates instead of serving yesterday's shell forever.
- **Accessibility:** the progress/result region is a live region, tables use row
  headers, and the results list announces itself as busy while processing.
- **Contributor tooling:** `tools/generate_icons.py` (reproducible icon set),
  `tools/dev_server.py` (serves `docs/` with `no-store`, because the service
  worker's cache-first behaviour otherwise hides your edits).
- Deep links for docs, screenshots and smoke tests: `?theme=dark&lang=en&demo=1`.

### Changed

- The `dev` extra now includes `hypothesis`, `zizmor` and `pip-audit`.
- Dependencies bumped to the versions Dependabot proposed: `ruff` 0.16.7,
  `mypy` 2.3.1, `pytest` 9, `pytest-cov` 7, `werkzeug` 3.1.8, `pillow-heif` 1.7.0.

## [0.3.0] — 2026-09-15

A full audit-response release: every critical finding from the code review is
fixed, and the project gains a zero-cost, zero-server deployment.

### Added — the offline web app (`docs/`)

- **100 % client-side PWA.** Drag & drop (desktop and mobile), paste, or pick
  files; photos are decoded with `createImageBitmap`, redrawn onto a fresh canvas
  and re-encoded with `toBlob`. Nothing ever leaves the device.
- **`connect-src 'none'` CSP** plus a "Try to send data" button that demonstrates
  the browser blocking the request. The Pages workflow greps the source and fails
  the build if a remote call ever appears.
- Red **GPS warning** with decimal coordinates, plus an optional map link.
- **Before/after comparison slider**, per-file download and **batch ZIP** export
  (vendored JSZip).
- Resize / quality / output-format controls, watermark with opacity and position.
- Persian (RTL) and English UI with a toggle, dark/light/auto themes.
- Service worker + manifest: installable and fully usable offline.
- Metadata inspector powered by vendored exifr, with personal chunks separated
  from harmless container headers.

### Fixed — critical

- **Portrait photos are no longer delivered sideways.** The EXIF orientation is
  baked into the pixels with `ImageOps.exif_transpose` *before* the tag is
  dropped (previously `100×50` with `Orientation=6` stayed `100×50` instead of
  becoming `50×100`). Opt out with `--no-auto-orient` / `auto_orient=False`.
- **A clean file is no longer reported as dirty.** JFIF headers, DPI, interlace,
  transparency and WebP `timestamp` are container fields, not user data; they are
  now listed under `technical` and no longer set `has_metadata`. The
  `removed`/`removed_count` fields now hold the **real tag names**
  (`Make`, `Model`, `GPSLatitude`, …) instead of category names.
- **The API binds `0.0.0.0` by default**, so the documented
  `docker run -p 5000:5000 … python -m api.server` is reachable from the host.
- **`img-clean` returns real exit codes.** The console script pointed at
  `cli.main:main`, whose return value Python discards — every failure exited `0`.
  It now points at `cli.main:cli`, which calls `sys.exit(main())`.
- **No metadata can leak through exotic modes.** The `img.copy()` fallback (which
  carries the `info` dict) is gone; every mode goes through a fresh canvas, and
  `I;16` PNGs keep their bit depth.
- **Removed dead code:** the `Image.MAX_IMAGE_PIXELS = Image.MAX_IMAGE_PIXELS`
  no-op, the unused `SUPPORTED_FORMATS` constant (now enforced), the unreachable
  duplicate `LA` branch, and the unused `_allowed()` helper (now used by the API).
- **The API no longer doubles memory use.** Uploads stream to disk in 64 KB
  chunks, validation parses the image once, and the result streams back from disk
  with the temp directory cleaned up when the response ends.

### Fixed — robustness

- **`-o` for a single file is taken literally**: `photo.jpg -o newdir` creates a
  file, not `newdir/photo_cleaned.jpg`. Trailing slash, an image extension, a
  directory, multiple inputs or a glob all mean "directory".
- **No more exponential file growth**: `*_cleaned.*` outputs are excluded when
  expanding globs and directories.
- `~` is expanded, directories can be passed as input, and multiple inputs are
  accepted on one command line.
- **Batch mode without `-o` is now guarded too** against overwriting existing
  files (`--overwrite` / `--skip-existing`), not just batch mode with `-o`.
- **The library refuses silent overwrites** (`FileExistsError`); only `overwrite=True`
  replaces an existing file.
- New CLI abilities: `--format` (JPG→PNG/WebP conversion), `--jobs`,
  `--progress` (stderr, so `--json` stays parseable), `--json`, `--opacity`,
  `--watermark-position`, `--keep-icc`, `--skip-existing`, `--no-recursive`.
- **The ICC colour profile can be preserved** with `--keep-icc` /
  `keep_icc=True` (default remains strip, and a kept profile does not fail the
  clean verification).
- **Animated WebP keeps every frame** instead of silently becoming a still image
  (JPEG output keeps the first frame and says so).
- **HEIC/HEIF input** is supported when the optional `pillow-heif` extra is
  installed, with a clear error message when it is not.
- **Persian/RTL watermarks are shaped correctly** via libraqm (falling back to
  `arabic-reshaper` + `python-bidi`), with a font stack that has real Arabic
  coverage, and configurable opacity and position.
- Unsupported formats now produce an actionable message listing what is
  supported, and `SN`-style aliases (e.g. Pillow reporting `MPO` for multi-picture
  JPEGs) are normalised to `JPEG`.

### Changed — packaging & tooling

- **Dependencies are pinned** in `requirements.txt` and `pyproject.toml`.
- **The Docker image installs the package** (`pip install .`), so `img-clean`
  exists inside it, and the default `CMD` is the API — matching the
  `HEALTHCHECK`, which therefore no longer always reports unhealthy.
- **CI** (`.github/workflows/ci.yml`): ruff lint + format check, mypy, pytest with
  coverage on Linux and Windows for Python 3.10 and 3.12, plus a Docker
  build/healthcheck job.
- **Release** (`.github/workflows/release.yml`): sdist + wheel, standalone
  PyInstaller CLI binaries for Linux/Windows/macOS, attached to a GitHub release.
- **Pages** (`.github/workflows/pages.yml`): deploys `docs/` with a privacy guard.
- **Dependabot** for pip, GitHub Actions and Docker; **issue templates** for bugs
  and features (the bug template that `CONTRIBUTING.md` referenced now exists);
  a **PR template**; group updates monthly/weekly.
- **`SECURITY.md`** now directs reports to a private GitHub Security Advisory
  instead of Telegram, and documents the threat model of both deployments.
- `pyproject.toml` gains ruff/mypy/pytest configuration and a valid PEP 639
  license expression (the legacy license classifier conflicted with it and broke
  `pip install .`).
- Tests grew from 12 to 52, covering orientation, honest metadata reporting, ICC
  retention, animation, RTL watermarks, exotic modes, CLI path/format/exit-code
  behaviour, API streaming/limits and packaging invariants.

## [0.2.0] — earlier

- Security hardening pass: input file never touched, API upload limits and
  validation, `secure_filename`, debug off, non-root Docker user.
- Bilingual README, SECURITY.md, CONTRIBUTING.md.

## [0.1.0] — initial

- EXIF/GPS analysis and cleaning, watermark, CLI, Flask API, Dockerfile.

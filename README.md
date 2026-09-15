# Image Metadata Cleaner

[![CI](https://github.com/Alvandcode/image-metadata-cleaner/actions/workflows/ci.yml/badge.svg)](https://github.com/Alvandcode/image-metadata-cleaner/actions/workflows/ci.yml)
[![Web app](https://img.shields.io/badge/web%20app-offline%20%C2%B7%20no%20upload-4cc9a0?style=flat-square)](https://alvandcode.github.io/image-metadata-cleaner/)
[![License](https://img.shields.io/github/license/Alvandcode/image-metadata-cleaner?style=flat-square)](./LICENSE)
[![Stars](https://img.shields.io/github/stars/Alvandcode/image-metadata-cleaner?style=flat-square)](https://github.com/Alvandcode/image-metadata-cleaner/stargazers)

> Remove EXIF and GPS metadata from photos — a privacy-first cleaner with a **100 % offline web app**, a CLI and an optional Flask API.

<div dir="rtl">

## پاک‌کننده متادیتای عکس

**عکس‌هایت را بدون هیچ آپلودی پاک کن.**

ابزار حفظ حریم خصوصی برای حذف کامل متادیتای EXIF، موقعیت GPS، مدل دوربین، XMP، IPTC و کامنت‌ها.
نسخه وب کاملاً داخل مرورگر کار می‌کند و هیچ بایتی از دستگاه شما خارج نمی‌شود؛ نسخه خط فرمان هم برای
پردازش گروهی، حفظ انیمیشن WebP، پروفایل رنگ دقیق و HEIC آیفون هست.

**ویژگی‌ها**

- 🌐 **نسخه وب بدون سرور** (`docs/`) — نصب‌شدنی (PWA)، کاملاً آفلاین، فارسی و انگلیسی، دارک‌مود
- 🔒 **بدون آپلود** — سیاست امنیتی صفحه `connect-src 'none'` است، پس حتی ارسال داده هم ممکن نیست
- 🧹 حذف کامل EXIF + GPS + ICC + XMP + کامنت (خروجی از پیکسل‌های تازه ساخته می‌شود، فایل ورودی دست‌نخورده می‌ماند)
- 🔄 **اصلاح خودکار جهت عکس** — عکس‌های عمودی گوشی دیگر کج تحویل داده نمی‌شوند
- ✅ **راستی‌آزمایی خروجی** — بعد از پاک‌سازی، خروجی دوباره تحلیل می‌شود تا مطمئن شویم چیزی باقی نمانده
- 🖼️ JPG · PNG · WebP (و HEIC با نصب اختیاری)
- ⚡ پردازش گروهی با `--jobs`، خروجی JSON، گزارش پیشرفت، تبدیل قالب و جلوگیری از بازنویسی
- 💧 واترمارک با پشتیبانی درست فارسی/RTL و شفافیت دلخواه
- 🎬 حفظ انیمیشن WebP
- 🐳 Docker (کاربر غیرروت + HEALTHCHECK سالم)، CI، Release و Dependabot

</div>

---

## 🚀 Quick start

### 1. Web app — recommended, nothing to install

👉 **https://alvandcode.github.io/image-metadata-cleaner/**

Photos are decoded in your browser, redrawn onto a fresh canvas and re-encoded.
There is **no backend at all**: the page's Content-Security-Policy sets
`connect-src 'none'`, so it is technically impossible for the app to send your
image anywhere. Turn off Wi-Fi and it keeps working (service worker cache).

You can confirm it yourself: press **"Try to send data"** in the app — the
browser blocks the request and the console logs a CSP violation.

### 2. CLI / library

```bash
git clone https://github.com/Alvandcode/image-metadata-cleaner.git
cd image-metadata-cleaner
pip install -e ".[dev]"        # or: pip install -r requirements.txt
img-clean --version
```

Or from PyPI (once published): `pip install image-metadata-cleaner`.

### 3. Docker (optional API)

```bash
docker build -t metadata-cleaner .
docker run --rm -p 5000:5000 metadata-cleaner          # API on :5000
docker run --rm -v "$(pwd):/work" -w /work metadata-cleaner img-clean photo.jpg -o clean.jpg
```

---

## 🖥️ CLI

```bash
# one file -> new file
img-clean photo.jpg -o clean.jpg

# single file -> a directory
img-clean photo.jpg -o cleaned/

# a whole folder (recursive), converted, in parallel, with progress
img-clean photos/ -o cleaned/ --format webp --jobs 4 --progress

# several files at once, and a glob
img-clean a.jpg b.jpg "vacation/*.png" -o cleaned/

# read-only metadata report (JSON for scripts)
img-clean photo.jpg --analyze --json

# tuned output
img-clean photo.jpg \
  --resize 1600x1200 \
  --watermark "© علیرضا" --opacity 0.4 --watermark-position bottom-right \
  --quality 88 --keep-icc --overwrite
```

### Options

| Option | Description | Example |
|---|---|---|
| `-o, --output` | Output file (single input) or directory (many) | `-o cleaned/` |
| `--analyze` | Show metadata only; modifies nothing | `--analyze` |
| `--resize` | Resize to fit exactly | `--resize 800x600` |
| `--watermark` | Watermark text (RTL/Persian aware) | `--watermark "© Name"` |
| `--opacity` | Watermark opacity, 0–1 | `--opacity 0.35` |
| `--watermark-position` | `bottom-right` (default), `bottom-left`, `bottom-center`, `top-right`, `top-left`, `top-center`, `center` | `--watermark-position center` |
| `--quality` | JPEG/WebP quality 1–100 | `--quality 90` |
| `--format` | Force output format, converts JPG→PNG etc. | `--format webp` |
| `--keep-icc` | Keep the embedded ICC colour profile | `--keep-icc` |
| `--no-auto-orient` | Do not bake EXIF orientation into pixels | `--no-auto-orient` |
| `--overwrite` | Replace existing outputs | `--overwrite` |
| `--skip-existing` | Leave files whose output already exists | `--skip-existing` |
| `--jobs` | Parallel workers for batch mode | `--jobs 4` |
| `--progress` | Progress on stderr (stdout stays clean for `--json`) | `--progress` |
| `--json` | Machine-readable output on stdout | `--json` |
| `--no-recursive` | Do not descend into sub-directories | `--no-recursive` |
| `-q, --quiet` | Only errors | `-q` |

### Behaviour worth knowing

- **`-o` is taken literally for a single file.** `img-clean photo.jpg -o newdir`
  creates a *file* called `newdir`; add a trailing slash (`-o newdir/`) or an
  image extension (`-o newdir.png`) to get a directory or a specific format.
  Multiple inputs, a glob or a directory always produce a directory.
- **Your own output is never re-processed.** `*_cleaned.*` files are skipped when
  you pass a glob or a folder, so running the same command twice cannot create
  `photo_cleaned_cleaned.jpg` chains.
- **Nothing is overwritten silently.** The library raises `FileExistsError`
  unless you pass `overwrite=True`; the CLI exits 1 and tells you to use
  `--overwrite` or `--skip-existing`.
- **Existing metadata is not reported as a leak.** A cleaned file re-analyses as
  `has_metadata: false`; harmless container headers (JFIF version, DPI,
  interlace, WebP `timestamp`) are listed separately under `technical`.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Success (and the output verified clean) |
| `1` | Processing failure, no match, refused overwrite, or an output that still contains metadata |
| `2` | Usage error (bad option value, unsupported format, unreadable input) |
| `130` | Interrupted (Ctrl-C) |

The `img-clean` console script returns these codes properly — CI and `&&`
chains can rely on it.

---

## 🐍 Library

```python
from cleaner.exif_cleaner import analyze_metadata, batch_clean, clean_metadata

report = analyze_metadata("photo.jpg")
# {'has_metadata': True, 'has_gps': True, 'gps_decimal': {'lat': 35.6892, 'lon': 51.389},
#  'metadata': {...}, 'technical': {...}, 'exif': {...}, 'gps': {...}, 'format': 'JPEG', ...}

result = clean_metadata(
    "photo.jpg",
    "clean.jpg",            # None -> "photo_cleaned.jpg"
    resize=(1600, 1200),
    watermark_text="© علیرضا",
    opacity=0.4,
    quality=90,
    auto_orient=True,       # bake EXIF orientation into the pixels
    keep_icc=False,         # True keeps the colour profile
    overwrite=False,        # refuse to replace an existing file
    verify=True,            # re-analyse our own output
)
assert result["verified"]["has_metadata"] is False

results = batch_clean(
    ["a.jpg", "b.png"],
    output_dir="cleaned",
    out_format="webp",
    jobs=4,
    skip_existing=True,
    progress=lambda done, total, path: print(f"{done}/{total} {path}"),
)  # never raises: one status dict per file ("success" / "skipped" / "failed")
```

Key result fields: `removed` (the **actual tag names** that were dropped),
`removed_count`, `removed_categories`, `kept` (e.g. a deliberately kept ICC
profile), `verified`, `auto_oriented`, `is_animated`, `frames`.

### Optional extras

```bash
pip install "image-metadata-cleaner[heic]"   # read iPhone HEIC/HEIF
```

Without it, HEIC files are rejected with a clear message instead of a traceback.
For fully correct Persian/Arabic watermark shaping, install Pillow built with
`libraqm` (all official wheels have it); otherwise `arabic-reshaper` + `python-bidi`
are used when present.

---

## 🌐 API (optional, self-hosted)

```bash
python -m api.server           # listens on 0.0.0.0:5000
HOST=127.0.0.1 PORT=8080 python -m api.server
```

`HOST` defaults to `0.0.0.0` so the documented `docker run -p 5000:5000` workflow
actually works; override it to bind locally. `FLASK_DEBUG=1` is the only way to
enable debug mode (never do that on a public host).

```bash
curl -X POST -F "image=@photo.jpg" http://localhost:5000/clean -o cleaned.jpg
curl -X POST -F "image=@photo.jpg" -F resize=1200x800 -F quality=85 \
     -F watermark="© Name" -F opacity=0.4 -F format=webp \
     http://localhost:5000/clean -o cleaned.webp
curl -X POST -F "image=@photo.jpg" http://localhost:5000/analyze
curl http://localhost:5000/health
```

`/clean` form fields: `watermark`, `opacity`, `resize` (`WxH`), `quality`,
`format` (`png|jpg|webp|heic`), `keep_icc=1`, `no_auto_orient=1`.

Response headers report what happened: `X-Removed-Count`, `X-Verified-Clean`,
`X-Auto-Oriented`, `X-Original-Format`.

Uploads are streamed to a temp file in 64 KB chunks, the clean copy is streamed
back from disk, and the temp directory is deleted when the response finishes —
so concurrent uploads do not multiply memory use.

Limits: 16 MB per upload (`MAX_UPLOAD_MB`), and jpg/png/webp (+heic with the
extra) only. This is a single-purpose tool: if you expose it publicly, put it
behind a reverse proxy with TLS, auth and rate limiting.

---

## 🔒 Security & privacy

- **The input file is never modified** — the output is always a new file built
  from fresh pixels.
- **Verification loop.** After writing, the output is re-analysed. The CLI prints
  `verify: clean …` and exits non-zero if anything personal survived.
- **The web app cannot upload.** Its CSP sets `connect-src 'none'`; the CI job
  that deploys it even greps the source for remote calls and fails the build if
  one appears. No CDN, no analytics, vendored JS (`docs/vendor/`, see
  `docs/vendor/README.md`).
- **API hardening.** 16 MB cap, extension allow-list, single-pass image
  validation, `secure_filename`, security headers, debug off by default,
  timeouts and no `eval`.
- **DoS guards.** Pillow's decompression-bomb protection, an explicit
  `MAX_PIXELS` output cap and `MAX_DIMENSION` for `--resize`.

Report vulnerabilities through a **private GitHub Security Advisory**
(<https://github.com/Alvandcode/image-metadata-cleaner/security/advisories/new>) —
never a public issue. Details in [`SECURITY.md`](./SECURITY.md).

---

## 🏗️ Why there is no required server

A privacy tool that asks you to trust someone else's server with your private
photos is a contradiction. Free hosting tiers sleep, get deleted or cost money,
and every hosted API is one more place your photo could be logged.

So the default deployment is **static files on GitHub Pages** — free forever, no
card, no sleep, no maintenance, and nothing to breach because there is no
backend. The Python package is kept for what a browser genuinely cannot do well:
massive batch jobs, exact colour profiles, WebP animation and HEIC input.

```
docs/                 100% client-side PWA (the primary product)
cleaner/              core library (analyze / clean / batch / watermark)
cli/                  img-clean
api/                  optional Flask API for Docker
```

## 🧑‍💻 Development

```bash
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest          # 52 tests
ruff check . && ruff format --check . && mypy
```

CI runs lint + typecheck + tests on Linux and Windows (Python 3.10 and 3.12),
plus a Docker build/healthcheck job. See [`CONTRIBUTING.md`](./CONTRIBUTING.md).

## 📄 License

MIT — see [LICENSE](./LICENSE). Vendored JS is attributed in
[`docs/vendor/README.md`](./docs/vendor/README.md).

## 📢 Contact

- Telegram: [t.me/a_c_official](https://t.me/a_c_official)
- GitHub: [github.com/Alvandcode](https://github.com/Alvandcode)

**ساخته شده با ❤️ برای جامعه ایرانی**

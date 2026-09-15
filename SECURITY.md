# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| `0.3.x` (latest `main`) | ✅ |
| `0.2.x` and older tags | ❌ (please upgrade) |

## Reporting a vulnerability

**Please do not open a public issue.**

Use GitHub's private channel:

👉 **https://github.com/Alvandcode/image-metadata-cleaner/security/advisories/new**

If you cannot use advisories, contact the maintainer on Telegram
([@a_c_official](https://t.me/a_c_official)) and say only that you have a
security report — send the details through the private advisory once opened.

Please include:

- affected version / commit,
- steps to reproduce,
- impact (e.g. metadata leak, DoS, code execution),
- a suggested fix if you have one,
- whether you want to be credited in the release notes.

I acknowledge reports within 72 hours and aim to publish a fix and a release as
soon as possible. Credit is given in the advisory and release notes unless you
prefer to stay anonymous.

## Threat model

The project has two very different deployments, with different trust levels.

### Web app (`docs/`, GitHub Pages) — nothing to attack server side

- **There is no backend.** All processing happens in the browser with Canvas.
- **No upload.** The page's Content-Security-Policy sets `connect-src 'none'`,
  so even a compromised script in the page cannot send your image anywhere.
- Your photos never leave the device, and they are not stored anywhere.
- The service worker caches only static assets, never image data.

### CLI, library, Docker API — you run it

In scope:

- **Metadata leaks**: any output that still carries EXIF/GPS/XMP/ICC/comment
  chunks. `clean_metadata()` re-analyses its own output and reports
  `verified.has_metadata`; a leak there is a security bug.
- **Input mutation**: the input file must never be modified or deleted.
- **API hardening**: `MAX_CONTENT_LENGTH` bypass, path traversal through
  `secure_filename`, SSRF/RCE through Flask `debug` mode, unbounded memory use
  from uploads.
- **DoS**: decompression bombs (`Image.MAX_IMAGE_PIXELS`, `MAX_PIXELS`),
  oversized `--resize` targets.

Out of scope:

- Someone with local read access to your original file seeing its metadata.
- Serving `api.server` directly to the public internet without a reverse proxy,
  TLS and rate limiting. It is a single-purpose tool, not a hardened public
  gateway: put it behind a proxy and add auth if you expose it.
- Anything in third-party vendored files under `docs/vendor/` — report those
  upstream (JSZip, exifr), but tell me too so I can ship an updated copy.

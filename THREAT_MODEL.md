# Threat model

What this project defends against, what it explicitly does not, and why the
central claim — *"we cannot see your photos"* — holds even when a dependency
turns hostile.

## The asset

A photo is not just pixels. A single JPEG from a phone can carry the exact GPS
position of someone's home, the camera serial number, the owner's name, the
original capture time, and a small preview thumbnail of a scene the owner
believed they had cropped out. The asset being protected is **that context**,
and secondarily the pixels themselves (a cleaner must not degrade or leak them).

## Adversaries

| # | Adversary | Goal | Handled by |
|---|---|---|---|
| 1 | Whoever receives the file afterwards | Learn where/when/how it was taken | The cleaning step itself |
| 2 | Passive network observer / ISP | See the photo at all | The web app never transmits it |
| 3 | A malicious or compromised dependency (JSZip, exifr, Pillow) | Exfiltrate a photo, phone home | CSP + no network surface (web); no network code path (CLI) |
| 4 | Someone with access to the hosted site | Serve modified code that uploads photos | Pinned deps, attested releases, `zizmor`-audited workflows, source in the open |
| 5 | Malicious input file | Exploit the parser (Pillow/piexif) | Version pinning + dependency audit; fuzzing is on the roadmap |

Out of scope: an attacker who already controls your device, your browser
extensions, or the clipboard; a compromised operating system; and anyone who
has the *original* file (cleaning a copy cannot recall what was already shared).

## Trust boundaries

```
                 ┌─────────────────────────────── browser (trusted by the user) ───────────────┐
  photo ──▶ drop │  app.js  ──▶  <canvas>  ──▶  toBlob  ──▶  download                          │
                 │     ▲                                                  no fetch / XHR /    │
                 │     └── exifr reads a copy, in memory, to *show* you    beacon to anywhere │
                 └─────────────────────────────────────────────────────────────────────────────┘
                     │
                     └─ CSP: default-src 'none'; connect-src 'none'; script-src 'self'

  photo ──▶ img-clean ──▶ Pillow decode ──▶ fresh frame ──▶ encode ──▶ filesystem
            (no sockets, no telemetry, input file opened read-only)

  photo ──▶ [self-hosted API only] ──▶ temp file ──▶ streamed out ──▶ temp deleted
```

The web app is the strong case: the code that would have to leak your photo runs
in a sandbox whose network allow-list is empty. The CLI is the strong case for
batch work: it links no HTTP client at all. The optional Flask API is the weak
case **by construction** — someone is running it, so the photo does travel to
it. See "Self-hosting the API" below.

## Why "even a poisoned dependency cannot exfiltrate" holds in the web app

1. `Content-Security-Policy: default-src 'none'` with `connect-src 'none'`
   blocks `fetch`, `XMLHttpRequest`, `sendBeacon`, WebSocket and EventSource to
   any origin — the browser refuses before the request is made. Vendored JSZip or
   exifr code cannot opt out of a CSP that the document declares.
2. `script-src 'self'` means no remote script can be introduced at runtime, so a
   compromised dependency cannot fetch a second stage.
3. `img-src 'self' blob: data:` and `form-action 'none'` close the remaining
   exfiltration channels (image-beacon, form POST).
4. The service worker's own requests are *not* covered by the page CSP — which
   is why `sw.js` is deliberately written to touch nothing but its own origin
   and to cache only shell assets; the Pages workflow greps the source and fails
   the build if a remote call appears in any `docs/*.js`.
5. Photo bytes are held in memory only. The single exception is a photo shared
   through the OS share sheet, which the service worker parks in the cache named
   `imc-shared` and the page deletes the moment it picks it up.

Residual risk: a browser bug that lets a page escape CSP, or an installed
extension with host permissions. Neither is something the app can fix.

## What the cleaning step guarantees (and what it does not)

Guaranteed: the output is built by drawing the decoded pixels onto a brand-new
frame and re-encoding, so no EXIF/GPS/XMP/IPTC/comment/thumbnail chunk, and no
unknown chunk, can survive. `analyze_metadata()` is re-run on the output
(`verify=True`) and the CLI exits non-zero if anything personal is still there.

Explicitly **not** guaranteed:

* **ICC colour profiles are dropped** by canvas output (sRGB), which can shift
  colour. Use `--keep-icc` with the CLI when exact colour matters.
* **Animated images are flattened** by the web app (canvas has no animation
  export); the CLI preserves WebP animation.
* **Re-encoding can enlarge a file** (PNG especially). The UI reports the delta.
* **`--resize` is a bounding box**, not an exact size: it keeps the aspect ratio
  and never enlarges. Distorting a photo to hit an exact size is not done on
  purpose.
* **HEIC** works only when `pillow-heif` is installed (CLI) or in Safari (web).
* Automatic orientation baking *changes pixel dimensions* of portrait photos —
  that is the point, but it surprises people comparing hashes.

## Self-hosting the API (`api/server.py`)

The API exists for people who want a service on their own machine, and it has a
different risk profile:

* The photo **does** leave your device and lands in the server's temporary
  directory. Run it only on a host you trust, ideally on loopback.
* Uploads are streamed to disk in 64 KiB chunks with a size cap
  (`MAX_CONTENT_LENGTH`) and a `secure_filename`-based extension allow-list.
* Temporary files are deleted after the response is streamed, but a crash can
  leave one behind. Treat the temp directory as sensitive.
* It has no authentication. Do not expose it to the internet as-is; put it
  behind a reverse proxy with auth if you must, and consider whether the web app
  (which needs no server) is simply the better answer.

## Verifying these claims yourself

* Read `docs/app.js` — it is plain ES2020, no build step, no minification.
* Open the site, press "Try to send data", and watch the browser refuse. Then
  open DevTools → Network and confirm zero requests beyond the page's own files.
* Compare the bytes GitHub Pages serves with the repository:

  ```sh
  git clone https://github.com/Alvandcode/image-metadata-cleaner && cd image-metadata-cleaner
  curl -s https://alvandcode.github.io/image-metadata-cleaner/app.js | diff - docs/app.js && echo identical
  ```

* Verify a downloaded release artifact:

  ```sh
  sha256sum -c SHA256SUMS.txt
  gh attestation verify img-clean-linux --repo Alvandcode/image-metadata-cleaner
  ```

* Run the suite on your own machine: `pytest` (includes property-based tests
  that assert nothing personal survives, and that the input file is untouched).

## Reporting

Found a hole in this model? See [SECURITY.md](SECURITY.md) — private advisory,
please, not a public issue.

# Web app (`docs/`) — the primary product

A **100 % client-side** metadata cleaner. No backend, no API, no build step:
the files in this folder are the whole application.

```
index.html              shell + Content-Security-Policy
styles.css              dark/light themes, RTL + LTR layout
app.js                  decode → fresh canvas → re-encode, metadata report, ZIP export
sw.js                   service worker (offline shell + share target); its cache
                        version is stamped with the commit id by the Pages workflow
manifest.json           PWA manifest (icons, screenshots, share_target)
icon.svg                vector icon (+ icon-maskable.svg)
icon-192/512.png        raster icons: Android and the install prompt
icon-maskable-512.png   safe-zone icon for Android's cropping
apple-touch-icon.png    opaque PNG, because iOS ignores SVG here
screenshot-wide.png     install-prompt screenshots (must match manifest sizes)
screenshot-narrow.png
vendor/                 JSZip + exifr, committed on purpose (see vendor/README.md)
.nojekyll               tell GitHub Pages not to run Jekyll
```

Every committed asset is reproducible: `tools/generate_icons.py` redraws the
PNGs, and the screenshots come from headless Chrome hitting the app's own deep
links (`?demo=1&theme=dark`). See `CONTRIBUTING.md` for the exact commands.

## Deep links

| URL | Effect |
|---|---|
| `?demo=1` | Builds the demo photo (with GPS) and cleans it, without clicking |
| `?theme=dark` / `?theme=light` / `?theme=auto` | Force a colour scheme |
| `?lang=en` / `?lang=fa` | Force a language |
| `?shared=1` | What the share target redirects to: pick up the shared photo |

These exist for docs, screenshots and smoke tests, and they override the stored
preference in `localStorage`.

## Privacy contract

This app processes photos that may contain your home address, so the guarantees
are enforced, not just promised:

1. **No upload.** The page CSP is
   `default-src 'none'; connect-src 'none'; …` — the browser refuses any network
   request the page tries to make. You can verify it live with the
   **"Try to send data"** button: the request is blocked and a CSP violation is
   logged.
2. **No third parties.** JSZip and exifr are vendored locally; there is no CDN,
   no font download, no analytics, no telemetry.
3. **No storage.** Photos live in memory for the duration of the tab. The service
   worker caches static assets only, never image data, and `localStorage` holds
   nothing but your language and theme choice.
4. **The original file is never modified.** Only a fresh canvas is re-encoded;
   downloads are new files.
5. **Enforced in CI.** `.github/workflows/pages.yml` greps `docs/*.js` and
   `docs/*.html` for `fetch`/`XMLHttpRequest`/`WebSocket`/`sendBeacon` calls to
   remote URLs and fails the deployment if one appears.

## Local development

Any static server works — `file://` also runs, minus the service worker:

```sh
python -m http.server 8777 --directory docs
# then open http://127.0.0.1:8777/
```

**Cache warning:** `sw.js` is cache-first, so after editing `app.js` or
`styles.css` bump `VERSION` in `sw.js` (e.g. `imc-v2`) or the browser keeps
serving the old copy. DevTools → Application → Service Workers → *Unregister* +
*Clear storage* also works.

There is a **"Create a demo photo with GPS"** button that builds an in-memory
JPEG with a hand-written `APP1/EXIF` segment (Make, Model, Software and real GPS
rationals) so you can exercise the whole flow — including the red GPS warning —
without any test asset in the repository.

## Deployment

Push to `main` touching `docs/**` and the Pages workflow publishes the folder to
<https://alvandcode.github.io/image-metadata-cleaner/>. Enable it once in
**Settings → Pages → Source: GitHub Actions**.

An optional second mirror is Cloudflare Pages (unlimited free bandwidth) with the
same build-free settings: root directory `docs`, no build command.

## Notes and limits

- Canvas output is always sRGB: the ICC profile is dropped by design. If exact
  colour matters, use the CLI with `--keep-icc`.
- Canvas cannot produce an animation, so animated WebP/GIF inputs are flattened to
  the first frame in the browser (the CLI preserves WebP animation).
- HEIC/HEIF can be *analysed*, but browsers other than Safari cannot decode it for
  canvas cleaning — the app says so and points at the CLI.
- `dir="auto"` is set on machine-readable values (coordinates, dimensions) so the
  RTL layout cannot reverse a latitude/longitude pair.

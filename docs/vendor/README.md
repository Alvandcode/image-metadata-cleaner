# Vendored dependencies

These files are committed on purpose so the app has **zero network dependencies**
at runtime. There is no CDN, no package manager and no analytics.

| File | Package | Version | License |
|---|---|---|---|
| `jszip.min.js` | [JSZip](https://github.com/Stuk/jszip) | 3.10.1 | MIT **or** GPLv3 (see `jszip.LICENSE.txt`) |
| `exifr.min.js` | [exifr](https://github.com/MikeKovarik/exifr) | 7.1.3 | MIT (see `exifr.LICENSE.txt`) |

Both expose globals: `window.JSZip` and `window.exifr`.

## What each one is used for

- **JSZip** — bundle the cleaned photos into one downloadable `.zip`.
  Compression is set to `STORE` because JPEG/PNG/WebP are already compressed.
- **exifr** — *read* metadata so the app can show you exactly what is inside your
  file (including the raw GPS coordinates) before it is removed. exifr never
  writes anything; removal is done by redrawing the pixels on a canvas.

## Refreshing

```sh
curl -fsSLo docs/vendor/jszip.min.js \
  https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js
curl -fsSLo docs/vendor/exifr.min.js \
  https://cdn.jsdelivr.net/npm/exifr@7.1.3/dist/full.umd.js
```

After refreshing, update the version numbers above, check the licenses are
unchanged, and load the page once with DevTools → Network to confirm no request
goes outside the origin. Dependabot does not track these files; bump them by hand.

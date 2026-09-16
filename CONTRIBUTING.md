# Contributing

Thanks for your interest! Issues and PRs are welcome.

## Ways to help

| I want to… | Do this |
|---|---|
| Report a bug | [Bug report template](https://github.com/Alvandcode/image-metadata-cleaner/issues/new?template=bug_report.yml) |
| Request a feature | [Feature request template](https://github.com/Alvandcode/image-metadata-cleaner/issues/new?template=feature_request.yml) |
| Report a vulnerability | 🔒 [Private security advisory](https://github.com/Alvandcode/image-metadata-cleaner/security/advisories/new) — **never a public issue** (see `SECURITY.md`) |
| Ask a question | [Discussions](https://github.com/Alvandcode/image-metadata-cleaner/discussions) |
| Improve translations | `docs/app.js` and the README — Persian and English live side by side |

## Project layout

```
cleaner/exif_cleaner.py   core library (analyze / clean / batch / watermark)
cli/main.py               img-clean command line interface
api/server.py             optional Flask API (Docker)
docs/                     100% client-side PWA (GitHub Pages) — the primary product
tools/                    dev-only helpers (dev server, icon generator)
tests/test_cleaner.py     regression suite
tests/test_properties.py  property-based guarantees (Hypothesis)
THREAT_MODEL.md           adversaries, trust boundaries, residual risks
```

## Local setup

```bash
git clone https://github.com/Alvandcode/image-metadata-cleaner.git
cd image-metadata-cleaner
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

Everything the CI runs:

```bash
ruff check .
ruff format --check .
mypy
pytest --cov=cleaner --cov=cli --cov=api --cov-fail-under=80
zizmor .github/workflows          # audits the workflows themselves
pip-audit --requirement requirements.txt
```

## Working on the web app

```bash
python tools/dev_server.py --port 8777     # serves docs/ with Cache-Control: no-store
```

Open <http://127.0.0.1:8777/>. Three things make this bearable:

- **Always use `tools/dev_server.py`, not `python -m http.server`.** The latter
  sends no cache headers, so the browser keeps serving an old `app.js` and your
  edit looks like it did nothing.
- **The service worker caches the shell.** It deliberately goes network-first on
  `localhost`/`127.0.0.1`, but if you ever see stale behaviour, clear it:
  DevTools → Application → Service Workers → Unregister, and clear storage.
- **Deep links avoid clicking.** `?demo=1` builds and cleans the demo photo,
  `?theme=dark|light` and `?lang=fa|en` force a state. Screenshots in
  `docs/screenshot-*.png` were produced exactly this way.

Regenerating committed assets (both need only Pillow):

```bash
python tools/generate_icons.py      # docs/icon-192.png, icon-512.png, maskable, apple-touch-icon
```

Screenshots (Chrome, headless — sizes must match `manifest.json`):

```bash
chrome --headless --hide-scrollbars --virtual-time-budget=40000 \
  --window-size=1280,1600 --screenshot=docs/screenshot-wide.png \
  "http://127.0.0.1:8777/?demo=1&theme=dark"
```

The `share_target` flow (share a photo from another app into the cleaner) can
only be exercised on an installed mobile PWA — the service worker handles the
POST to `/share`, parks the bytes in the `imc-shared` cache and redirects to the
app with `?shared=1`. Desktop Chrome can install the PWA as a share destination,
which is the quickest way to sanity-check it.

## Releasing

1. Bump `__version__` in `cleaner/__init__.py` (the only place it lives) and add
   a `CHANGELOG.md` entry.
2. `git tag vX.Y.Z && git push origin vX.Y.Z`.

The `Release` workflow then builds the sdist/wheel, the three standalone
binaries, attests all of them, generates an SBOM and checksums, publishes to
PyPI and pushes the container image to GHCR. It fails on purpose if the tag and
the packaged version disagree.

### First PyPI release (one-time setup)

Nothing is stored in the repository — PyPI trusts the workflow's OIDC identity:

1. On PyPI, go to *Account → Publishing → Add a pending publisher*, choose
   GitHub, and fill in owner `Alvandcode`, repository `image-metadata-cleaner`,
   workflow `release.yml` (leave the environment empty).
2. Push a `v*` tag. No API token or secret is needed anywhere.

Until step 1 is done the `publish-pypi` job fails on tag pushes; the rest of the
release still succeeds.

## Guidelines

- Keep PRs small and focused; one behaviour change per PR.
- Add a test for every bug fix — the regression suite is the contract.
- **Preserve the privacy promise.** The web app must never upload, never call a
  remote origin, and must keep working offline. The Python library must rebuild
  pixels rather than surgically delete tags, and must never modify the input.
- Update the README (both languages) and `docs/` when user-visible behaviour
  changes.
- Use English for code, comments, commit messages, issues and PRs.
- Be respectful to other contributors.

## Commit messages

`feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:` — short imperative
subject, then a body explaining *why*.

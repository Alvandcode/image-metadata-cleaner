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
tests/test_cleaner.py     regression suite
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
pytest
```

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

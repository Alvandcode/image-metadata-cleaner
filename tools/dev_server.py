"""Static server for ``docs/`` while working on the PWA.

``python -m http.server`` sends no ``Cache-Control``, so browsers cache
``app.js``/``styles.css`` heuristically and an edit appears to do nothing until
a hard reload — which is easy to mistake for a bug in the app. This serves the
same directory with ``Cache-Control: no-store``.

    .venv/Scripts/python.exe tools/dev_server.py --port 8777
"""

from __future__ import annotations

import argparse
import functools
import http.server
import pathlib


class NoStoreHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def log_message(self, fmt: str, *args: object) -> None:  # keep the log quiet
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8777)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--directory", default="docs")
    args = parser.parse_args()

    handler = functools.partial(NoStoreHandler, directory=args.directory)
    with http.server.ThreadingHTTPServer((args.bind, args.port), handler) as httpd:
        where = pathlib.Path(args.directory).resolve()
        print(f"serving {where} on http://{args.bind}:{args.port}/ (no-store)")
        httpd.serve_forever()


if __name__ == "__main__":
    main()

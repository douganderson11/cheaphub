#!/usr/bin/env python3
"""Serve the static site and apply Netlify-style _redirects (including /go/)."""

from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def load_redirects() -> list[tuple[str, str, int]]:
    rules: list[tuple[str, str, int]] = []
    for raw in (ROOT / "_redirects").read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        source, dest = parts[0], parts[1]
        status = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 301
        rules.append((source, dest, status))
    return rules


class Handler(SimpleHTTPRequestHandler):
    redirects = load_redirects()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        path = unquote(self.path.split("?", 1)[0])
        for source, dest, status in self.redirects:
            if path == source:
                self.send_response(status)
                self.send_header("Location", dest)
                self.end_headers()
                return
        super().do_GET()


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve CheapHub with /go/ redirects")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Serving CheapHub at http://{args.host}:{args.port}/")
    server.serve_forever()


if __name__ == "__main__":
    main()

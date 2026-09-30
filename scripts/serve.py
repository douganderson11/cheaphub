#!/usr/bin/env python3
"""Serve the static site and apply Netlify-style _redirects (including /go/)."""

from __future__ import annotations

import argparse
import json
import subprocess
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

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

    def _redirect(self) -> bool:
        path = unquote(self.path.split("?", 1)[0])
        for source, dest, status in self.redirects:
            if path == source:
                self.send_response(status)
                self.send_header("Location", dest)
                self.end_headers()
                return True
        return False

    def _node(self, script: str, args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["node", str(ROOT / "netlify" / "functions" / script), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(ROOT),
        )

    def _deal_search(self, query: str) -> bool:
        q = parse_qs(query).get("q", [""])[0]
        try:
            result = self._node("deal-search.mjs", ["search", q], timeout=20)
        except subprocess.TimeoutExpired:
            body = {"error": "The price check didn't finish. Try again in a moment.", "results": [], "unchecked": [], "skipped": []}
            self._json(504, body)
            return True
        if result.returncode not in (0, 1) or not result.stdout.strip():
            self._json(500, {"error": "The price check didn't finish. Try again in a moment.", "results": [], "unchecked": [], "skipped": []})
            return True
        try:
            body = json.loads(result.stdout)
        except json.JSONDecodeError:
            self._json(500, {"error": "The price check didn't finish. Try again in a moment.", "results": [], "unchecked": [], "skipped": []})
            return True
        status = 400 if body.get("error") and not body.get("results") else 200
        self._json(status, body)
        return True

    def _go_out(self, query: str) -> bool:
        token = parse_qs(query).get("u", [""])[0]
        try:
            result = self._node("outbound.mjs", ["redirect", token], timeout=5)
        except subprocess.TimeoutExpired:
            self.send_error(504)
            return True
        destination = result.stdout.strip()
        if result.returncode != 0 or not destination.startswith("https://"):
            self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"That link isn't a product page we can open.")
            return True
        self.send_response(302)
        self.send_header("Location", destination)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        return True

    def _json(self, status: int, body: dict) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        path = unquote(parsed.path)
        if path == "/api/deal-search":
            self._deal_search(parsed.query)
            return
        if path.rstrip("/") == "/go/out":
            self._go_out(parsed.query)
            return
        if not self._redirect():
            super().do_GET()

    def do_HEAD(self) -> None:
        if not self._redirect():
            super().do_HEAD()


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

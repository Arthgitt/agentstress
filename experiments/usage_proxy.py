"""Local metering proxy in front of the OpenAI API.

Every framework's model traffic goes through 127.0.0.1, so token usage is
counted the same way for all three regardless of what each SDK exposes, and a
run can be stopped before it passes a spending cap. Request bodies can also be
kept, to verify prompt text on the hosted model exactly as on Ollama.
"""
from __future__ import annotations

import json
import ssl
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import certifi

# This Python build has no system CA bundle, so verify against certifi's.
_TLS = ssl.create_default_context(cafile=certifi.where())

# gpt-5.4-mini, $ per million tokens (OpenAI pricing page, fetched 2026-09-13).
PRICE_IN, PRICE_CACHED_IN, PRICE_OUT = 0.75, 0.075, 4.50

_lock = threading.Lock()
TOTALS = {"requests": 0, "input": 0, "cached_input": 0, "output": 0, "no_usage": 0, "http_errors": 0}
CAPTURE: list[dict] = []
KEEP_BODIES = {"on": False}


def cost(t: dict = TOTALS) -> float:
    fresh = t["input"] - t["cached_input"]
    return (fresh * PRICE_IN + t["cached_input"] * PRICE_CACHED_IN + t["output"] * PRICE_OUT) / 1e6


def snapshot() -> dict:
    with _lock:
        return dict(TOTALS)


def _usage_from(body: bytes, content_type: str) -> dict | None:
    try:
        if "event-stream" in content_type:
            usage = None
            for line in body.decode().splitlines():
                if line.startswith("data:") and line[5:].strip() not in ("", "[DONE]"):
                    u = json.loads(line[5:]).get("usage")
                    usage = u or usage
            return usage
        return json.loads(body).get("usage")
    except (ValueError, UnicodeDecodeError):
        return None


class _Handler(BaseHTTPRequestHandler):
    upstream = "https://api.openai.com"

    def log_message(self, *a):
        pass

    def _forward(self, method: str):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        if body and KEEP_BODIES["on"]:
            try:
                CAPTURE.append({"path": self.path, "body": json.loads(body)})
            except ValueError:
                pass
        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in ("host", "content-length", "accept-encoding", "connection")}
        req = urllib.request.Request(self.upstream + self.path, data=body, method=method, headers=headers)
        try:
            resp = urllib.request.urlopen(req, timeout=300, context=_TLS)
            status, data, rheaders = resp.status, resp.read(), resp.getheaders()
        except urllib.error.HTTPError as e:
            status, data, rheaders = e.code, e.read(), e.headers.items()
            with _lock:
                TOTALS["http_errors"] += 1
        ctype = dict((k.lower(), v) for k, v in rheaders).get("content-type", "")
        if method == "POST" and status == 200:
            u = _usage_from(data, ctype)
            with _lock:
                TOTALS["requests"] += 1
                if u:
                    TOTALS["input"] += u.get("prompt_tokens", 0)
                    TOTALS["output"] += u.get("completion_tokens", 0)
                    TOTALS["cached_input"] += (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0
                else:
                    TOTALS["no_usage"] += 1
        self.send_response(status)
        for k, v in rheaders:
            if k.lower() not in ("transfer-encoding", "connection", "content-length", "content-encoding"):
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        self._forward("POST")

    def do_GET(self):
        self._forward("GET")


def start(port: int = 11600) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

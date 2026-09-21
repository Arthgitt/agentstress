"""Logging proxy that records exactly what a framework sends the model.

Sits in front of the local Ollama endpoint, forwards every request unchanged and
keeps the request bodies. The study used it to establish that the three
frameworks send different scaffolding text for identical tasks; `agentstress
capture` exposes it to users for their own configuration.
"""
from __future__ import annotations

import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import agentstress.run_config as rc

PORT = 11500
LOG: list[dict] = []
CURRENT = {"fw": None}


def upstream() -> str:
    return rc.OLLAMA_BASE_URL


class Proxy(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _forward(self, method):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0)) if method == "POST" else None
        if body:
            try:
                LOG.append({"framework": CURRENT["fw"], "path": self.path, "body": json.loads(body)})
            except json.JSONDecodeError:
                pass
        req = urllib.request.Request(upstream() + self.path, data=body, method=method,
                                     headers={"Content-Type": self.headers.get("Content-Type", "application/json")})
        with urllib.request.urlopen(req, timeout=600) as r:
            data = r.read()
            self.send_response(r.status)
            for k, v in r.getheaders():
                if k.lower() not in ("transfer-encoding", "connection", "content-length"):
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    def do_POST(self):
        self._forward("POST")

    def do_GET(self):
        self._forward("GET")



def start(port: int = PORT) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Proxy)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

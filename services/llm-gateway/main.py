from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from caipture.llm_gateway import LlmGateway


class Handler(BaseHTTPRequestHandler):
    gateway = LlmGateway(enabled=os.getenv("CAIPTURE_LLM_ENABLED", "false").lower() == "true")

    def _respond(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._respond(HTTPStatus.OK, {"status": "ok"})
            return
        self._respond(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/summarize":
            self._respond(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        result = self.gateway.summarize_context(body.get("text", ""))
        self._respond(HTTPStatus.OK, result)


def main() -> None:
    host = os.getenv("CAIPTURE_LLM_HOST", "127.0.0.1")
    port = int(os.getenv("CAIPTURE_LLM_PORT", "8090"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"llm-gateway listening on {host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from caipture.pipeline import Pipeline


class Handler(BaseHTTPRequestHandler):
    pipeline = Pipeline(os.getenv("CAIPTURE_CONFIG"))

    def _json_response(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_json(self) -> dict:
        size = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(size) if size else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._json_response(HTTPStatus.OK, {"status": "ok"})
            return
        if self.path.startswith("/jobs/"):
            job_id = self.path.split("/jobs/", 1)[1]
            job = self.pipeline.queue.fetch_job(job_id)
            if not job:
                self._json_response(HTTPStatus.NOT_FOUND, {"error": "job not found"})
                return
            self._json_response(HTTPStatus.OK, job)
            return
        self._json_response(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        try:
            if self.path == "/upload":
                body = self._read_json()
                result = self.pipeline.create_job(
                    front_path=body["front_path"],
                    back_path=body["back_path"],
                    context_paths=body.get("context_paths", []),
                )
                self._json_response(HTTPStatus.CREATED, result)
                return
            if self.path == "/run-all-once":
                self._json_response(HTTPStatus.OK, self.pipeline.run_all_once())
                return
            if self.path.startswith("/review/"):
                job_id = self.path.split("/review/", 1)[1]
                body = self._read_json()
                self.pipeline.apply_review(job_id, body.get("approved_by", "reviewer"), body.get("notes", ""))
                self._json_response(HTTPStatus.OK, {"ok": True})
                return
        except Exception as exc:  # pragma: no cover
            self._json_response(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._json_response(HTTPStatus.NOT_FOUND, {"error": "not found"})


def main() -> None:
    host = os.getenv("CAIPTURE_WEB_HOST", "127.0.0.1")
    port = int(os.getenv("CAIPTURE_WEB_PORT", "8080"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"web listening on {host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()

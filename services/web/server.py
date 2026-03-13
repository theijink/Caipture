from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from caipture.pipeline import Pipeline


def _is_pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _http_health(url: str, timeout_s: float = 1.0) -> str:
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as response:
            if 200 <= response.status < 300:
                return "up"
            return f"down_http_{response.status}"
    except urllib.error.URLError:
        return "down"


class Handler(BaseHTTPRequestHandler):
    pipeline = Pipeline(os.getenv("CAIPTURE_CONFIG"))

    def _json_response(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _html_response(self, status: int, html: str) -> None:
        payload = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_json(self) -> dict:
        size = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(size) if size else b"{}"
        return json.loads(raw.decode("utf-8"))

    def _monitoring_payload(self) -> dict:
        config = self.pipeline.config
        jobs = self.pipeline.queue.list_jobs()
        status_counts: dict[str, int] = {}
        for job in jobs:
            status_counts[job["status"]] = status_counts.get(job["status"], 0) + 1

        processes = {
            "running": status_counts.get("processing", 0),
            "finished": status_counts.get("completed", 0),
            "aborted": status_counts.get("failed", 0) + status_counts.get("validation_failed", 0),
            "possible_queue": status_counts.get("queued", 0) + status_counts.get("uploaded", 0) + status_counts.get("review_required", 0),
        }

        monitoring_cfg = config.get("monitoring", {})
        runtime_dir = Path(monitoring_cfg.get("runtime_dir", Path(config["storage"]["root"]) / "runtime"))
        service_pidfiles = {
            "web": runtime_dir / "web.pid",
            "worker_cv": runtime_dir / "worker-cv.pid",
            "worker_ocr": runtime_dir / "worker-ocr.pid",
            "worker_metadata": runtime_dir / "worker-metadata.pid",
            "worker_export": runtime_dir / "worker-export.pid",
            "llm_gateway": runtime_dir / "llm-gateway.pid",
        }
        services = {}
        for service_name, pidfile in service_pidfiles.items():
            if not pidfile.exists():
                services[service_name] = "unknown"
                continue
            try:
                pid = int(pidfile.read_text(encoding="utf-8").strip())
            except ValueError:
                services[service_name] = "unknown"
                continue
            services[service_name] = "running" if _is_pid_running(pid) else "stopped"

        llm_health_url = monitoring_cfg.get("llm_gateway_health_url", "http://127.0.0.1:8090/health")
        services["llm_gateway_http"] = _http_health(llm_health_url)

        apps = {
            "queue_db": "up" if Path(config["queue"]["db_path"]).exists() else "down",
            "storage_root": "up" if Path(config["storage"]["root"]).exists() else "down",
            "web_api": "up",
        }

        try:
            one, five, fifteen = os.getloadavg()
            load = {
                "load1": round(one, 2),
                "load5": round(five, 2),
                "load15": round(fifteen, 2),
                "cpu_count": os.cpu_count(),
            }
        except OSError:
            load = {
                "load1": None,
                "load5": None,
                "load15": None,
                "cpu_count": os.cpu_count(),
            }

        metrics = self.pipeline.metrics.snapshot()

        return {
            "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "services": services,
            "applications": apps,
            "llm_usage_since_start": {
                "started_at": metrics.get("started_at"),
                "requests_total": metrics.get("llm_requests_total", 0),
                "provider_calls": metrics.get("llm_enabled_requests", 0),
            },
            "job_counts": status_counts,
            "processes": processes,
            "system_load": load,
            "stage_totals": metrics.get("stages", {}),
        }

    def _render_dashboard(self, payload: dict) -> str:
        refresh_s = int(self.pipeline.config.get("monitoring", {}).get("refresh_seconds", 5))
        services_rows = "".join([f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in payload["services"].items()])
        apps_rows = "".join([f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in payload["applications"].items()])
        status_rows = "".join([f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in payload["job_counts"].items()])
        stage_rows = "".join([f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in payload["stage_totals"].items()])

        return f"""<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <meta http-equiv=\"refresh\" content=\"{refresh_s}\" />
  <title>Caipture Monitoring</title>
  <style>
    body {{ font-family: sans-serif; margin: 24px; background: #f7f7f7; color: #111; }}
    h1 {{ margin-bottom: 8px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(280px,1fr)); gap: 12px; }}
    .card {{ background: white; border-radius: 8px; padding: 12px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
    table {{ width: 100%; border-collapse: collapse; }}
    td {{ border-bottom: 1px solid #eee; padding: 6px; }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
  </style>
</head>
<body>
  <h1>Caipture Monitoring</h1>
  <p class=\"mono\">Updated: {payload['timestamp']}</p>
  <div class=\"grid\">
    <div class=\"card\"><h3>Service Status</h3><table>{services_rows}</table></div>
    <div class=\"card\"><h3>Application Status</h3><table>{apps_rows}</table></div>
    <div class=\"card\"><h3>LLM Usage Since Session Start</h3>
      <p>Started: <span class=\"mono\">{payload['llm_usage_since_start']['started_at']}</span></p>
      <p>Requests: <strong>{payload['llm_usage_since_start']['requests_total']}</strong></p>
      <p>Provider calls: <strong>{payload['llm_usage_since_start']['provider_calls']}</strong></p>
    </div>
    <div class=\"card\"><h3>Processes</h3>
      <p>Running: <strong>{payload['processes']['running']}</strong></p>
      <p>Finished: <strong>{payload['processes']['finished']}</strong></p>
      <p>Aborted: <strong>{payload['processes']['aborted']}</strong></p>
      <p>Possible queue: <strong>{payload['processes']['possible_queue']}</strong></p>
    </div>
    <div class=\"card\"><h3>Job Status Counts</h3><table>{status_rows}</table></div>
    <div class=\"card\"><h3>Stage Totals</h3><table>{stage_rows}</table></div>
    <div class=\"card\"><h3>System Load</h3>
      <p>load1: {payload['system_load']['load1']}</p>
      <p>load5: {payload['system_load']['load5']}</p>
      <p>load15: {payload['system_load']['load15']}</p>
      <p>cpu_count: {payload['system_load']['cpu_count']}</p>
    </div>
  </div>
</body>
</html>
"""

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._json_response(HTTPStatus.OK, {"status": "ok"})
            return
        if self.path == "/monitoring":
            self._json_response(HTTPStatus.OK, self._monitoring_payload())
            return
        if self.path == "/":
            payload = self._monitoring_payload()
            self._html_response(HTTPStatus.OK, self._render_dashboard(payload))
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
    pipeline = Handler.pipeline
    host = os.getenv("CAIPTURE_WEB_HOST", pipeline.config.get("web", {}).get("host", "127.0.0.1"))
    port = int(os.getenv("CAIPTURE_WEB_PORT", str(pipeline.config.get("web", {}).get("port", 8080))))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"web listening on {host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()

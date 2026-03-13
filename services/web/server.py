from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from caipture.journal import Journal
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


def _pid_resource_usage(pid: int) -> dict[str, float | int | None]:
    # macOS-compatible lightweight process stats.
    try:
        out = subprocess.run(
            ["ps", "-p", str(pid), "-o", "%cpu=,rss="],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if not out:
            return {"cpu_percent": None, "rss_kb": None}
        parts = out.split()
        if len(parts) < 2:
            return {"cpu_percent": None, "rss_kb": None}
        return {"cpu_percent": float(parts[0]), "rss_kb": int(parts[1])}
    except Exception:
        return {"cpu_percent": None, "rss_kb": None}


def _parse_multipart_form(content_type: str, body: bytes) -> tuple[dict[str, str], dict[str, list[dict[str, Any]]]]:
    boundary_match = re.search(r"boundary=([^;]+)", content_type)
    if not boundary_match:
        raise ValueError("multipart boundary missing")
    boundary = boundary_match.group(1).strip().strip('"').encode("utf-8")
    delimiter = b"--" + boundary
    fields: dict[str, str] = {}
    files: dict[str, list[dict[str, Any]]] = {}

    for raw_part in body.split(delimiter):
        part = raw_part.strip(b"\r\n")
        if not part or part == b"--":
            continue

        header_blob, sep, content = part.partition(b"\r\n\r\n")
        if not sep:
            continue
        content = content.rstrip(b"\r\n")

        headers: dict[str, str] = {}
        for line in header_blob.decode("utf-8", errors="replace").split("\r\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        disposition = headers.get("content-disposition", "")
        name_match = re.search(r'name="([^"]+)"', disposition)
        if not name_match:
            continue
        field_name = name_match.group(1)

        filename_match = re.search(r'filename="([^"]*)"', disposition)
        if filename_match:
            filename = Path(filename_match.group(1)).name
            files.setdefault(field_name, []).append(
                {
                    "filename": filename,
                    "content_type": headers.get("content-type", "application/octet-stream"),
                    "content": content,
                }
            )
        else:
            fields[field_name] = content.decode("utf-8", errors="replace")

    return fields, files


class Handler(BaseHTTPRequestHandler):
    pipeline = Pipeline(os.getenv("CAIPTURE_CONFIG"))

    def _runtime_dir(self) -> Path:
        cfg = self.pipeline.config
        return Path(cfg.get("monitoring", {}).get("runtime_dir", Path(cfg["storage"]["root"]) / "runtime"))

    def _journal(self) -> Journal:
        return Journal(self._runtime_dir() / "journal.jsonl")

    def _log_action(self, action: str, details: dict[str, Any] | None = None) -> None:
        self._journal().log("web", action, details or {})

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

    def _read_form(self) -> dict[str, str]:
        size = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(size) if size else b""
        parsed = urllib.parse.parse_qs(raw.decode("utf-8", errors="replace"))
        return {k: v[0] for k, v in parsed.items() if v}

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
        runtime_dir = self._runtime_dir()
        service_pidfiles = {
            "web": runtime_dir / "web.pid",
            "worker_cv": runtime_dir / "worker-cv.pid",
            "worker_ocr": runtime_dir / "worker-ocr.pid",
            "worker_metadata": runtime_dir / "worker-metadata.pid",
            "worker_export": runtime_dir / "worker-export.pid",
            "llm_gateway": runtime_dir / "llm-gateway.pid",
        }
        services: dict[str, dict[str, Any]] = {}
        process_metrics: dict[str, dict[str, float | int | None]] = {}
        for service_name, pidfile in service_pidfiles.items():
            if not pidfile.exists():
                services[service_name] = {"status": "unknown", "pid": None}
                continue
            try:
                pid = int(pidfile.read_text(encoding="utf-8").strip())
            except ValueError:
                services[service_name] = {"status": "unknown", "pid": None}
                continue
            status = "running" if _is_pid_running(pid) else "stopped"
            services[service_name] = {"status": status, "pid": pid}
            process_metrics[service_name] = _pid_resource_usage(pid)

        llm_health_url = monitoring_cfg.get("llm_gateway_health_url", "http://127.0.0.1:8090/health")
        services["llm_gateway_http"] = {"status": _http_health(llm_health_url), "pid": None}

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
        recent_actions = self._journal().tail(25)

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
            "process_metrics": process_metrics,
            "stage_totals": metrics.get("stages", {}),
            "recent_actions": recent_actions,
            "jobs": jobs,
        }

    def _render_bars(self, processes: dict[str, int]) -> str:
        max_val = max(1, max(processes.values()))
        bars = []
        for key in ["running", "finished", "aborted", "possible_queue"]:
            value = int(processes.get(key, 0))
            width = int((value / max_val) * 100)
            bars.append(
                f"<div class='bar-row'><span>{key}</span><div class='bar'><div class='fill' style='width:{width}%;'></div></div><strong>{value}</strong></div>"
            )
        return "".join(bars)

    def _render_process_load_bars(self, process_metrics: dict[str, dict[str, float | int | None]]) -> str:
        cpu_values = [float(v.get("cpu_percent", 0.0) or 0.0) for v in process_metrics.values()]
        max_cpu = max(1.0, max(cpu_values) if cpu_values else 1.0)
        rows = []
        for name, metric in process_metrics.items():
            cpu = float(metric.get("cpu_percent", 0.0) or 0.0)
            rss_mb = round(float(metric.get("rss_kb", 0) or 0) / 1024.0, 1)
            width = int((cpu / max_cpu) * 100)
            rows.append(
                f"<div class='bar-row'><span>{name}</span><div class='bar'><div class='fill cpu' style='width:{width}%;'></div></div><strong>{cpu:.1f}% / {rss_mb:.1f}MB</strong></div>"
            )
        return "".join(rows) if rows else "<p>No running process metrics available.</p>"

    def _render_dashboard(self, payload: dict) -> str:
        refresh_s = int(self.pipeline.config.get("monitoring", {}).get("refresh_seconds", 5))
        services_rows = "".join(
            [
                f"<tr><td>{name}</td><td>{meta.get('status')}</td><td>{meta.get('pid') or '-'}</td><td><a href='/monitoring'>view</a></td></tr>"
                for name, meta in payload["services"].items()
            ]
        )
        apps_rows = "".join([f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in payload["applications"].items()])
        status_rows = "".join([f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in payload["job_counts"].items()])
        stage_rows = "".join([f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in payload["stage_totals"].items()])
        action_rows = "".join(
            [
                f"<tr><td>{a.get('timestamp')}</td><td>{a.get('source')}</td><td>{a.get('action')}</td><td><code>{json.dumps(a.get('details', {}))}</code></td></tr>"
                for a in payload["recent_actions"][-15:]
            ]
        )
        job_rows = []
        for job in payload["jobs"][-25:]:
            approve_html = ""
            if job.get("status") == "review_required":
                approve_html = (
                    "<form action='/approve-web' method='post'>"
                    f"<input type='hidden' name='job_id' value='{job.get('job_id')}' />"
                    "<input type='hidden' name='approved_by' value='web-user' />"
                    "<button type='submit'>Approve</button></form>"
                )
            job_rows.append(
                "<tr>"
                f"<td><a href='/jobs/{job.get('job_id')}'>{job.get('job_id')}</a></td>"
                f"<td>{job.get('status')}</td>"
                f"<td>{job.get('item_id')}</td>"
                f"<td>{approve_html}</td>"
                "</tr>"
            )
        jobs_table = "".join(job_rows) if job_rows else "<tr><td colspan='4'>No jobs yet</td></tr>"
        proc_load = self._render_process_load_bars(payload.get("process_metrics", {}))

        return f"""<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <meta http-equiv=\"refresh\" content=\"{refresh_s}\" />
  <title>Caipture Control Center</title>
  <style>
    :root {{
      --bg:#0b1020; --card:#141b33; --text:#e2e8f0; --muted:#94a3b8; --border:#334155;
      --barbg:#1e293b; --accent1:#22d3ee; --accent2:#4ade80;
    }}
    @media (prefers-color-scheme: light) {{
      :root {{ --bg:#f5f8fb; --card:#ffffff; --text:#0f172a; --muted:#334155; --border:#e2e8f0; --barbg:#e2e8f0; --accent1:#0ea5e9; --accent2:#22c55e; }}
    }}
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 20px; background: var(--bg); color: var(--text); }}
    h1 {{ margin: 0 0 8px; }}
    .sub {{ color: var(--muted); margin-bottom: 14px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(320px,1fr)); gap: 12px; }}
    .card {{ background: var(--card); border-radius: 10px; padding: 12px; border:1px solid var(--border); }}
    table {{ width: 100%; border-collapse: collapse; }}
    td {{ border-bottom: 1px solid var(--border); padding: 6px; vertical-align: top; }}
    a {{ color: var(--accent1); }}
    .mono, code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }}
    .bar-row {{ display: grid; grid-template-columns: 120px 1fr 40px; gap: 8px; align-items: center; margin: 6px 0; }}
    .bar {{ background: var(--barbg); height: 12px; border-radius: 10px; overflow: hidden; }}
    .fill {{ background: linear-gradient(90deg,var(--accent1),var(--accent2)); height: 100%; }}
    .fill.cpu {{ background: linear-gradient(90deg,#fb7185,#f59e0b); }}
    .actions {{ max-height: 520px; overflow: auto; grid-column: span 2; }}
    form label {{ display: block; margin: 8px 0 2px; font-weight: 600; }}
    input[type=file], input[type=text], button {{ width: 100%; padding: 8px; box-sizing: border-box; border-radius:6px; border:1px solid var(--border); background:transparent; color:var(--text); }}
    button {{ margin-top: 10px; background: #0f766e; color: white; border: 0; border-radius: 6px; cursor: pointer; }}
  </style>
</head>
<body>
  <h1>Caipture Control Center</h1>
  <div class=\"sub\">Updated: <span class=\"mono\">{payload['timestamp']}</span></div>

  <div class=\"grid\">
    <div class=\"card\">
      <h3>Upload Via Web Page</h3>
      <form action=\"/upload-web\" method=\"post\" enctype=\"multipart/form-data\">
        <label>Front image</label>
        <input type=\"file\" name=\"front_file\" required />
        <label>Back image</label>
        <input type=\"file\" name=\"back_file\" required />
        <label>Context images (optional)</label>
        <input type=\"file\" name=\"context_files\" multiple />
        <label>Auto run pipeline once after upload</label>
        <input type=\"text\" name=\"auto_run\" value=\"true\" />
        <button type=\"submit\">Upload Job</button>
      </form>
    </div>

    <div class=\"card\"><h3>Service Status</h3><table><tr><td><strong>service</strong></td><td><strong>status</strong></td><td><strong>pid</strong></td><td><strong>link</strong></td></tr>{services_rows}</table></div>
    <div class=\"card\"><h3>Application Status</h3><table>{apps_rows}</table></div>

    <div class=\"card\"><h3>LLM Usage Since Session Start</h3>
      <p>Started: <span class=\"mono\">{payload['llm_usage_since_start']['started_at']}</span></p>
      <p>Requests: <strong>{payload['llm_usage_since_start']['requests_total']}</strong></p>
      <p>Provider calls: <strong>{payload['llm_usage_since_start']['provider_calls']}</strong></p>
    </div>

    <div class=\"card\"><h3>Process Overview</h3>{self._render_bars(payload['processes'])}</div>
    <div class=\"card\"><h3>System Load per Relevant Process</h3>{proc_load}</div>

    <div class=\"card\"><h3>Job Status Counts</h3><table>{status_rows}</table></div>
    <div class=\"card\"><h3>Stage Totals</h3><table>{stage_rows}</table></div>
    <div class=\"card\"><h3>Jobs Queue and Approval</h3><table><tr><td><strong>job_id</strong></td><td><strong>status</strong></td><td><strong>item</strong></td><td><strong>actions</strong></td></tr>{jobs_table}</table></div>

    <div class=\"card\"><h3>System Load</h3>
      <p>load1: {payload['system_load']['load1']}</p>
      <p>load5: {payload['system_load']['load5']}</p>
      <p>load15: {payload['system_load']['load15']}</p>
      <p>cpu_count: {payload['system_load']['cpu_count']}</p>
    </div>

    <div class=\"card actions\"><h3>Recent Journal Actions</h3><p><a href='/journal'>open full journal feed</a></p>
      <table>
        <tr><td><strong>timestamp</strong></td><td><strong>source</strong></td><td><strong>action</strong></td><td><strong>details</strong></td></tr>
        {action_rows}
      </table>
    </div>
  </div>
</body>
</html>
"""

    def do_GET(self) -> None:  # noqa: N802
        self._log_action("http_get", {"path": self.path})
        if self.path == "/health":
            self._json_response(HTTPStatus.OK, {"status": "ok"})
            return
        if self.path == "/monitoring":
            self._json_response(HTTPStatus.OK, self._monitoring_payload())
            return
        if self.path == "/journal":
            self._json_response(HTTPStatus.OK, {"entries": self._journal().tail(500)})
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
        self._log_action("http_post", {"path": self.path})
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

            if self.path == "/approve-web":
                form = self._read_form()
                job_id = form.get("job_id", "")
                approved_by = form.get("approved_by", "web-user")
                if not job_id:
                    self._json_response(HTTPStatus.BAD_REQUEST, {"error": "job_id is required"})
                    return
                self.pipeline.apply_review(job_id, approved_by=approved_by, notes="approved via web")
                self._html_response(
                    HTTPStatus.OK,
                    "<html><body><h2>Job approved</h2><p><a href='/'>Back to dashboard</a></p></body></html>",
                )
                return

            if self.path == "/upload-web":
                content_type = self.headers.get("Content-Type", "")
                length = int(self.headers.get("Content-Length", "0"))
                body_raw = self.rfile.read(length)
                fields, files = _parse_multipart_form(content_type, body_raw)
                if "front_file" not in files or "back_file" not in files:
                    self._json_response(HTTPStatus.BAD_REQUEST, {"error": "front_file and back_file are required"})
                    return

                runtime_upload_dir = self._runtime_dir() / "web_uploads"
                runtime_upload_dir.mkdir(parents=True, exist_ok=True)

                def _save_file(file_item: dict[str, Any], prefix: str) -> Path:
                    suffix = Path(file_item["filename"] or "upload.bin").suffix or ".bin"
                    fd, tmp_path = tempfile.mkstemp(prefix=f"{prefix}_", suffix=suffix, dir=runtime_upload_dir)
                    os.close(fd)
                    p = Path(tmp_path)
                    p.write_bytes(file_item["content"])
                    return p

                front_path = _save_file(files["front_file"][0], "front")
                back_path = _save_file(files["back_file"][0], "back")
                context_paths = []
                for idx, c in enumerate(files.get("context_files", []), start=1):
                    context_paths.append(str(_save_file(c, f"context_{idx:03d}")))

                result = self.pipeline.create_job(str(front_path), str(back_path), context_paths)

                auto_run = fields.get("auto_run", "true").strip().lower() in {"1", "true", "yes", "y"}
                if auto_run:
                    run = self.pipeline.run_all_once()
                    self._log_action("web_upload_auto_run", {"job_id": result["job_id"], "run": run})

                html = (
                    "<html><body>"
                    f"<h2>Upload successful</h2><p>job_id: <code>{result['job_id']}</code></p>"
                    "<p><a href='/'>Back to dashboard</a></p>"
                    f"<p><a href='/jobs/{result['job_id']}'>View job JSON</a></p>"
                    "</body></html>"
                )
                self._html_response(HTTPStatus.CREATED, html)
                return

            if self.path == "/run-all-once":
                result = self.pipeline.run_all_once()
                self._json_response(HTTPStatus.OK, result)
                return

            if self.path.startswith("/review/"):
                job_id = self.path.split("/review/", 1)[1]
                body = self._read_json()
                self.pipeline.apply_review(job_id, body.get("approved_by", "reviewer"), body.get("notes", ""))
                self._json_response(HTTPStatus.OK, {"ok": True})
                return
        except Exception as exc:  # pragma: no cover
            self._log_action("http_error", {"path": self.path, "error": str(exc)})
            self._json_response(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._json_response(HTTPStatus.NOT_FOUND, {"error": "not found"})


def main() -> None:
    pipeline = Handler.pipeline
    host = os.getenv("CAIPTURE_WEB_HOST", pipeline.config.get("web", {}).get("host", "127.0.0.1"))
    port = int(os.getenv("CAIPTURE_WEB_PORT", str(pipeline.config.get("web", {}).get("port", 8080))))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"web listening on {host}:{port}")
    Journal(Path(pipeline.config.get("monitoring", {}).get("runtime_dir", "storage/runtime")) / "journal.jsonl").log(
        "web", "startup", {"host": host, "port": port}
    )
    server.serve_forever()


if __name__ == "__main__":
    main()

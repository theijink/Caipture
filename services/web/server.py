from __future__ import annotations

import json
import mimetypes
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from email.parser import BytesParser
from email.policy import default
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
    if "multipart/form-data" not in content_type:
        raise ValueError("expected multipart/form-data")

    envelope = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
    msg = BytesParser(policy=default).parsebytes(envelope)

    fields: dict[str, str] = {}
    files: dict[str, list[dict[str, Any]]] = {}
    for part in msg.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        name = part.get_param("name", header="content-disposition")
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        ctype = part.get_content_type()
        if not name:
            continue
        if filename:
            files.setdefault(name, []).append(
                {
                    "filename": Path(filename).name,
                    "content_type": ctype,
                    "content": payload,
                }
            )
        else:
            fields[name] = payload.decode("utf-8", errors="replace")
    return fields, files


def _safe_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


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

    def _redirect(self, location: str, status: int = HTTPStatus.SEE_OTHER) -> None:
        self.send_response(status)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _read_json(self) -> dict:
        size = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(size) if size else b"{}"
        return json.loads(raw.decode("utf-8"))

    def _read_form(self) -> dict[str, str]:
        size = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(size) if size else b""
        parsed = urllib.parse.parse_qs(raw.decode("utf-8", errors="replace"))
        return {k: v[0] for k, v in parsed.items() if v}

    def _job_export_paths(self, job_id: str) -> dict[str, Path]:
        base = Path(self.pipeline.config["storage"]["root"]) / "jobs" / job_id / "exports"
        return {
            "image": base / "photo_export.png",
            "sidecar": base / "photo_export.sidecar.json",
        }

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

        llm_health_url = config.get("monitoring", {}).get("llm_gateway_health_url", "http://127.0.0.1:8090/health")
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
            load = {"load1": None, "load5": None, "load15": None, "cpu_count": os.cpu_count()}

        metrics = self.pipeline.metrics.snapshot()
        recent_actions = list(reversed(self._journal().tail(200)))

        jobs_out = []
        for job in jobs:
            exports = self._job_export_paths(job["job_id"])
            jobs_out.append(
                {
                    **job,
                    "export_available": exports["image"].exists(),
                    "sidecar_available": exports["sidecar"].exists(),
                }
            )

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
            "jobs": jobs_out,
        }

    def _render_bars(self, values: dict[str, int], cls: str = "") -> str:
        if not values:
            return ""
        max_val = max(1, max(int(v) for v in values.values()))
        bars = []
        for key, value in values.items():
            width = int((int(value) / max_val) * 100)
            bars.append(
                f"<div class='bar-row'><span>{key}</span><div class='bar'><div class='fill {cls}' style='width:{width}%;'></div></div><strong>{value}</strong></div>"
            )
        return "".join(bars)

    def _render_process_load_bars(self, process_metrics: dict[str, dict[str, float | int | None]]) -> str:
        cpu_map = {name: round(float((m.get("cpu_percent") or 0.0)), 2) for name, m in process_metrics.items()}
        if not cpu_map:
            return "<p>No running process metrics available.</p>"
        return self._render_bars({k: int(v * 10) for k, v in cpu_map.items()}, cls="cpu")

    def _render_dashboard(self, payload: dict, message: str = "") -> str:
        services_rows = "".join(
            [
                "<tr>"
                f"<td><span class='led {('ok' if meta.get('status')=='running' else 'warn')}'></span>{name}</td>"
                f"<td>{meta.get('status')}</td>"
                f"<td>{meta.get('pid') or '-'}</td>"
                f"<td><button class='inline' onclick=\"openModalFromUrl('/process/{name}')\">view</button></td>"
                "</tr>"
                for name, meta in payload["services"].items()
            ]
        )
        apps_rows = "".join([f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in payload["applications"].items()])
        status_rows = "".join([f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in payload["job_counts"].items()])
        stage_rows = "".join([f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in payload["stage_totals"].items()])

        action_rows = "".join(
            [
                f"<tr><td>{a.get('timestamp')}</td><td>{a.get('source')}</td><td>{a.get('action')}</td><td><code>{_safe_json(a.get('details', {}))}</code></td></tr>"
                for a in payload["recent_actions"][:200]
            ]
        )

        job_rows = []
        for job in sorted(payload["jobs"], key=lambda j: j.get("created_at", ""), reverse=True)[:300]:
            approve_html = ""
            if job.get("status") == "review_required":
                approve_html = (
                    f"<button class='inline' onclick=\"approveJob('{job.get('job_id')}')\">Approve</button>"
                )
            export_html = "-"
            if job.get("export_available"):
                export_html = (
                    f"<button class='inline' onclick=\"openModalHtmlFromUrl('/preview/{job.get('job_id')}/image')\">preview image</button> "
                    f"<button class='inline' onclick=\"openModalFromUrl('/preview/{job.get('job_id')}/metadata')\">preview metadata</button> "
                    f"<a href='/download/{job.get('job_id')}/image'>download image</a> | "
                    f"<a href='/download/{job.get('job_id')}/sidecar'>download metadata</a>"
                )
            links = (
                f"<button class='inline' onclick=\"openModalFromUrl('/jobs/{job.get('job_id')}')\">job</button> "
                f"<button class='inline' onclick=\"openModalFromUrl('/jobs/{job.get('job_id')}/events')\">events</button>"
            )
            delete_btn = f"<button class='danger inline' onclick=\"deleteJob('{job.get('job_id')}')\">Delete</button>"
            job_rows.append(
                "<tr>"
                f"<td>{job.get('job_id')}</td>"
                f"<td>{job.get('status')}</td>"
                f"<td>{links}</td>"
                f"<td>{approve_html}</td>"
                f"<td>{export_html}</td>"
                f"<td>{delete_btn}</td>"
                "</tr>"
            )
        jobs_table = "".join(job_rows) if job_rows else "<tr><td colspan='6'>No jobs yet</td></tr>"

        banner = f"<div class='flash'>{message}</div>" if message else ""

        return f"""<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Caipture Control Center</title>
  <style>
    :root {{
      --bg:#eef3f8; --card:#ffffff; --text:#0f172a; --muted:#334155; --border:#cdd7e4;
      --barbg:#e2e8f0; --accent1:#0ea5e9; --accent2:#22c55e; --danger:#dc2626;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg:#0a1020; --card:#141b33; --text:#e2e8f0; --muted:#94a3b8; --border:#334155;
        --barbg:#1e293b; --accent1:#22d3ee; --accent2:#4ade80; --danger:#f87171;
      }}
    }}
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 20px; background: radial-gradient(circle at top right, rgba(14,165,233,.12), transparent 40%), var(--bg); color: var(--text); }}
    h1 {{ margin: 0 0 8px; }}
    .sub {{ color: var(--muted); margin-bottom: 14px; display:flex; gap:14px; align-items:center; }}
    .flash {{ padding:8px 10px; border:1px solid var(--border); border-radius:8px; margin-bottom:10px; background:var(--card); }}
    .grid {{ display: grid; grid-template-columns: 1.35fr 1fr 1fr; gap: 12px; }}
    .card {{ background: var(--card); border-radius: 10px; padding: 12px; border:1px solid var(--border); }}
    .wide {{ grid-column: span 3; }}
    .journal {{ grid-column: span 3; min-height: 740px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    td {{ border-bottom: 1px solid var(--border); padding: 6px; vertical-align: top; }}
    a {{ color: var(--accent1); }}
    .mono, code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }}
    .bar-row {{ display: grid; grid-template-columns: 150px 1fr 70px; gap: 8px; align-items: center; margin: 6px 0; }}
    .bar {{ background: var(--barbg); height: 12px; border-radius: 10px; overflow: hidden; }}
    .fill {{ background: linear-gradient(90deg,var(--accent1),var(--accent2)); height: 100%; }}
    .fill.cpu {{ background: linear-gradient(90deg,#fb7185,#f59e0b); }}
    .actions {{ max-height: 680px; overflow: auto; }}
    form label {{ display: block; margin: 8px 0 2px; font-weight: 600; }}
    input[type=file], input[type=text], input[type=date], textarea, button {{ width: 100%; padding: 8px; box-sizing: border-box; border-radius:6px; border:1px solid var(--border); background:transparent; color:var(--text); }}
    textarea {{ min-height: 72px; resize: vertical; }}
    button {{ margin-top: 8px; background: #0f766e; color: white; border: 0; border-radius: 6px; cursor: pointer; }}
    button.inline {{ width:auto; margin:0; padding:5px 9px; }}
    button.danger {{ background: var(--danger); }}
    .led {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:6px; box-shadow:0 0 8px currentColor; }}
    .led.ok {{ color:#22c55e; background:#22c55e; }}
    .led.warn {{ color:#f59e0b; background:#f59e0b; }}
    .modal-bg {{ display:none; position:fixed; inset:0; background:rgba(0,0,0,.55); z-index:9999; }}
    .modal {{ width:min(1100px,94vw); max-height:88vh; overflow:auto; margin:4vh auto; background:var(--card); border:1px solid var(--border); border-radius:10px; padding:12px; }}
    pre {{ white-space:pre-wrap; word-break:break-word; }}
    .preview img {{ max-width:100%; height:auto; border:1px solid var(--border); border-radius:8px; }}
  </style>
  <script>
    function openModalText(text) {{
      const bg = document.getElementById('modal-bg');
      const textBody = document.getElementById('modal-body-text');
      const htmlBody = document.getElementById('modal-body-html');
      htmlBody.style.display = 'none';
      textBody.style.display = 'block';
      textBody.textContent = text;
      bg.style.display = 'block';
    }}
    function openModalHtml(html) {{
      const bg = document.getElementById('modal-bg');
      const textBody = document.getElementById('modal-body-text');
      const htmlBody = document.getElementById('modal-body-html');
      textBody.style.display = 'none';
      htmlBody.style.display = 'block';
      htmlBody.innerHTML = html;
      bg.style.display = 'block';
    }}
    function closeModal() {{
      document.getElementById('modal-bg').style.display = 'none';
    }}
    async function openModalFromUrl(url) {{
      const res = await fetch(url);
      const txt = await res.text();
      openModalText(txt);
    }}
    async function openModalHtmlFromUrl(url) {{
      const res = await fetch(url);
      const txt = await res.text();
      openModalHtml(txt);
    }}
    async function apiPost(path, payload) {{
      const res = await fetch(path, {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify(payload || {{}}),
      }});
      const text = await res.text();
      return {{ok: res.ok, status: res.status, text: text}};
    }}
    async function approveJob(jobId) {{
      const r = await apiPost('/approve-web', {{job_id: jobId, approved_by: 'web-user', notes: 'approved via dashboard'}});
      if (!r.ok) {{ openModalText(r.text); return; }}
      location.reload();
    }}
    async function deleteJob(jobId) {{
      if (!confirm('Delete job ' + jobId + '? This removes inputs and outputs.')) return;
      const r = await apiPost('/delete-web', {{job_id: jobId}});
      if (!r.ok) {{ openModalText(r.text); return; }}
      location.reload();
    }}
  </script>
</head>
<body>
  <h1>Caipture Control Center</h1>
  {banner}
  <div class=\"sub\">Updated: <span class=\"mono\">{payload['timestamp']}</span> <button class='inline' onclick=\"location.reload()\">Refresh</button></div>

  <div class=\"grid\">
    <div class=\"card\">
      <h3>Upload (Camera/File)</h3>
      <form action=\"/upload-web\" method=\"post\" enctype=\"multipart/form-data\">
        <label>Subject image (required)</label>
        <input type=\"file\" name=\"subject_file\" accept=\"image/*\" capture=\"environment\" required />
        <label>Back image (optional)</label>
        <input type=\"file\" name=\"back_file\" accept=\"image/*\" capture=\"environment\" />
        <label>Context images (optional)</label>
        <input type=\"file\" name=\"context_files\" accept=\"image/*\" capture=\"environment\" multiple />
        <label>Manual date (optional)</label>
        <input type=\"date\" name=\"manual_date\" />
        <label>Manual location (optional)</label>
        <input type=\"text\" name=\"manual_location\" placeholder=\"City, country\" />
        <label>Manual comment/description (optional)</label>
        <textarea name=\"manual_comment\" placeholder=\"People, event, notes\"></textarea>
        <label>Auto run pipeline once after upload</label>
        <input type=\"text\" name=\"auto_run\" value=\"true\" />
        <button type=\"submit\">Upload Job</button>
      </form>
    </div>

    <div class=\"card\"><h3>Service Status</h3><table><tr><td><strong>service</strong></td><td><strong>status</strong></td><td><strong>pid</strong></td><td><strong>action</strong></td></tr>{services_rows}</table></div>
    <div class=\"card\"><h3>Application Status</h3><table>{apps_rows}</table></div>

    <div class=\"card\"><h3>LLM Usage Since Session Start</h3>
      <p>Started: <span class=\"mono\">{payload['llm_usage_since_start']['started_at']}</span></p>
      <p>Requests: <strong>{payload['llm_usage_since_start']['requests_total']}</strong></p>
      <p>Provider calls: <strong>{payload['llm_usage_since_start']['provider_calls']}</strong></p>
      <p><button onclick=\"openModalFromUrl('/monitoring')\">Open full monitoring JSON</button></p>
    </div>

    <div class=\"card\"><h3>Process Overview</h3>{self._render_bars(payload['processes'])}</div>
    <div class=\"card\"><h3>System Load per Service</h3>{self._render_process_load_bars(payload['process_metrics'])}</div>

    <div class=\"card\"><h3>Job Status Counts</h3><table>{status_rows}</table></div>
    <div class=\"card\"><h3>Stage Totals</h3><table>{stage_rows}</table></div>

    <div class=\"card wide\"><h3>Jobs Queue, Links, Actions</h3>
      <table>
        <tr><td><strong>job_id</strong></td><td><strong>status</strong></td><td><strong>details</strong></td><td><strong>approve</strong></td><td><strong>preview/export</strong></td><td><strong>delete</strong></td></tr>
        {jobs_table}
      </table>
    </div>

    <div class=\"card journal\"><h3>Recent Journal Actions (newest first)</h3>
      <p><button onclick=\"openModalFromUrl('/journal')\">Open full journal feed</button></p>
      <div class=\"actions\">
        <table>
          <tr><td><strong>timestamp</strong></td><td><strong>source</strong></td><td><strong>action</strong></td><td><strong>details</strong></td></tr>
          {action_rows}
        </table>
      </div>
    </div>
  </div>

  <div id=\"modal-bg\" class=\"modal-bg\" onclick=\"closeModal()\">
    <div class=\"modal\" onclick=\"event.stopPropagation()\">
      <p><button class='inline' onclick=\"closeModal()\">Close</button></p>
      <pre id=\"modal-body-text\"></pre>
      <div id=\"modal-body-html\" class=\"preview\" style=\"display:none\"></div>
    </div>
  </div>
</body>
</html>
"""

    def _send_file(self, path: Path, download_name: str, inline: bool = False) -> None:
        data = path.read_bytes()
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        disposition = "inline" if inline else "attachment"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f"{disposition}; filename={download_name}")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        self._log_action("http_get", {"path": self.path})

        if self.path == "/health":
            self._json_response(HTTPStatus.OK, {"status": "ok"})
            return
        if self.path == "/monitoring":
            self._json_response(HTTPStatus.OK, self._monitoring_payload())
            return
        if self.path == "/journal":
            self._json_response(HTTPStatus.OK, {"entries": list(reversed(self._journal().tail(1000)))})
            return

        if self.path.startswith("/process/"):
            name = self.path.split("/process/", 1)[1]
            payload = self._monitoring_payload()
            self._json_response(HTTPStatus.OK, {"service": name, "status": payload["services"].get(name), "metric": payload["process_metrics"].get(name)})
            return

        if self.path.startswith("/download/"):
            parts = self.path.strip("/").split("/")
            if len(parts) == 3:
                _, job_id, kind = parts
                paths = self._job_export_paths(job_id)
                if kind in paths and paths[kind].exists():
                    self._send_file(paths[kind], paths[kind].name)
                    return
            self._json_response(HTTPStatus.NOT_FOUND, {"error": "artifact not found"})
            return

        if self.path.startswith("/preview/"):
            m = re.match(r"^/preview/([^/]+)/(image|metadata)$", self.path)
            if not m:
                self._json_response(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            job_id, kind = m.group(1), m.group(2)
            paths = self._job_export_paths(job_id)
            if kind == "image":
                if not paths["image"].exists():
                    self._html_response(HTTPStatus.NOT_FOUND, "<p>Image not available.</p>")
                    return
                html = (
                    f"<h3>Export preview: {job_id}</h3>"
                    f"<p><img src='/download/{job_id}/image' alt='export image' /></p>"
                    f"<p><a href='/download/{job_id}/image' target='_blank'>open image in new tab</a></p>"
                )
                self._html_response(HTTPStatus.OK, html)
                return
            if not paths["sidecar"].exists():
                self._json_response(HTTPStatus.NOT_FOUND, {"error": "metadata not available"})
                return
            self._json_response(HTTPStatus.OK, json.loads(paths["sidecar"].read_text(encoding="utf-8")))
            return

        if self.path.startswith("/jobs/"):
            suffix = self.path.split("/jobs/", 1)[1]
            if suffix.endswith("/events"):
                job_id = suffix[: -len("/events")]
                self._json_response(HTTPStatus.OK, {"job_id": job_id, "events": self.pipeline.queue.fetch_events(job_id)})
                return
            job_id = suffix
            job = self.pipeline.queue.fetch_job(job_id)
            if not job:
                self._json_response(HTTPStatus.NOT_FOUND, {"error": "job not found"})
                return
            self._json_response(HTTPStatus.OK, job)
            return

        if self.path.startswith("/"):
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.path == "/":
                msg = urllib.parse.parse_qs(parsed.query).get("msg", [""])[0]
                payload = self._monitoring_payload()
                self._html_response(HTTPStatus.OK, self._render_dashboard(payload, message=msg))
                return

        self._json_response(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        self._log_action("http_post", {"path": self.path})
        try:
            if self.path == "/upload":
                body = self._read_json()
                subject_path = body.get("subject_path") or body.get("front_path")
                if not subject_path:
                    self._json_response(HTTPStatus.BAD_REQUEST, {"error": "subject_path is required"})
                    return
                manual_context = body.get("manual_context")
                if not isinstance(manual_context, dict):
                    manual_context = {
                        "date": body.get("manual_date", ""),
                        "location": body.get("manual_location", ""),
                        "comment": body.get("manual_comment") or body.get("manual_description", ""),
                    }
                result = self.pipeline.create_job(
                    subject_path=subject_path,
                    back_path=body.get("back_path"),
                    context_paths=body.get("context_paths", []),
                    manual_context=manual_context,
                )
                self._json_response(HTTPStatus.CREATED, result)
                return

            if self.path == "/approve-web":
                ctype = self.headers.get("Content-Type", "")
                if "application/json" in ctype:
                    body = self._read_json()
                    job_id = body.get("job_id", "")
                    approved_by = body.get("approved_by", "web-user")
                    notes = body.get("notes", "approved via web")
                else:
                    form = self._read_form()
                    job_id = form.get("job_id", "")
                    approved_by = form.get("approved_by", "web-user")
                    notes = form.get("notes", "approved via web")
                if not job_id:
                    self._json_response(HTTPStatus.BAD_REQUEST, {"error": "job_id is required"})
                    return
                self.pipeline.apply_review(job_id, approved_by=approved_by, notes=notes)
                self._json_response(HTTPStatus.OK, {"ok": True, "job_id": job_id})
                return

            if self.path == "/delete-web":
                ctype = self.headers.get("Content-Type", "")
                if "application/json" in ctype:
                    body = self._read_json()
                    job_id = body.get("job_id", "")
                else:
                    form = self._read_form()
                    job_id = form.get("job_id", "")
                if not job_id:
                    self._json_response(HTTPStatus.BAD_REQUEST, {"error": "job_id is required"})
                    return
                deleted = self.pipeline.delete_job(job_id)
                self._json_response(HTTPStatus.OK, {"ok": deleted, "job_id": job_id})
                return

            if self.path == "/upload-web":
                content_type = self.headers.get("Content-Type", "")
                length = int(self.headers.get("Content-Length", "0"))
                body_raw = self.rfile.read(length)
                fields, files = _parse_multipart_form(content_type, body_raw)
                if "subject_file" not in files:
                    self._json_response(HTTPStatus.BAD_REQUEST, {"error": "subject_file is required"})
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

                subject_path = _save_file(files["subject_file"][0], "subject")

                back_path: str | None = None
                if files.get("back_file"):
                    back_path = str(_save_file(files["back_file"][0], "back"))

                context_paths = []
                for idx, c in enumerate(files.get("context_files", []), start=1):
                    context_paths.append(str(_save_file(c, f"context_{idx:03d}")))

                manual_context = {
                    "date": fields.get("manual_date", "").strip(),
                    "location": fields.get("manual_location", "").strip(),
                    "comment": (fields.get("manual_comment", "") or fields.get("manual_description", "")).strip(),
                }

                result = self.pipeline.create_job(
                    subject_path=str(subject_path),
                    back_path=back_path,
                    context_paths=context_paths,
                    manual_context=manual_context,
                )
                auto_run = fields.get("auto_run", "true").strip().lower() in {"1", "true", "yes", "y"}
                if auto_run:
                    run = self.pipeline.run_all_once()
                    self._log_action("web_upload_auto_run", {"job_id": result["job_id"], "run": run})

                self._redirect(f"/?msg=Upload+successful:+{result['job_id']}")
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

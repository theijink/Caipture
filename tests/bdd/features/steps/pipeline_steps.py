from __future__ import annotations

import json
import tempfile
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

from behave import given, then, when

from caipture.pipeline import Pipeline
from services.web.server import Handler
from tests.test_utils import make_jpeg, make_png


def _make_config(root: Path, cv_min_bytes: int) -> Path:
    cfg = {
        "web": {"host": "127.0.0.1", "port": 8080},
        "monitoring": {
            "runtime_dir": str(root / "storage" / "runtime"),
            "llm_gateway_health_url": "http://127.0.0.1:8090/health",
            "refresh_seconds": 1,
        },
        "storage": {"root": str(root / "storage")},
        "upload": {"allowed_image_formats": ["png", "jpg", "jpeg"], "min_longest_side_px": 300},
        "cv": {"engine": "cv", "min_short_side_px": 900, "min_bytes": cv_min_bytes},
        "ocr": {"engine": "ocr", "language": "eng"},
        "metadata": {
            "pipeline_version": "0.2.0",
            "config_version": "bdd",
            "enable_llm_gateway": False,
            "location_dictionary": {
                "enschede": {
                    "name": "Enschede, Overijssel, Netherlands",
                    "country_code": "NL",
                    "lat": 52.2215,
                    "lon": 6.8937,
                }
            },
        },
        "review": {"auto_approve_min_confidence": 0.75},
        "export": {"profile": "default"},
        "queue": {"db_path": str(root / "storage" / "runtime" / "jobs.sqlite3"), "max_retries": 2},
    }
    path = root / "config.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return path


def _build_multipart(fields: dict[str, str], files: dict[str, tuple[str, bytes, str]]) -> tuple[bytes, str]:
    boundary = f"----caipture-{uuid4().hex}"
    lines: list[bytes] = []

    for key, value in fields.items():
        lines.append(f"--{boundary}".encode())
        lines.append(f'Content-Disposition: form-data; name="{key}"'.encode())
        lines.append(b"")
        lines.append(value.encode())

    for field_name, (filename, content, content_type) in files.items():
        lines.append(f"--{boundary}".encode())
        lines.append(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"'.encode())
        lines.append(f"Content-Type: {content_type}".encode())
        lines.append(b"")
        lines.append(content)

    lines.append(f"--{boundary}--".encode())
    lines.append(b"")
    body = b"\r\n".join(lines)
    return body, boundary


@given("a temporary Caipture test environment")
def step_env_default(context) -> None:
    context._tmpdir = tempfile.TemporaryDirectory()
    context.root = Path(context._tmpdir.name)
    context.config_path = _make_config(context.root, cv_min_bytes=10)
    context.pipeline = Pipeline(context.config_path)


@given("a temporary Caipture test environment with CV min bytes {min_bytes:d}")
def step_env_custom(context, min_bytes: int) -> None:
    context._tmpdir = tempfile.TemporaryDirectory()
    context.root = Path(context._tmpdir.name)
    context.config_path = _make_config(context.root, cv_min_bytes=min_bytes)
    context.pipeline = Pipeline(context.config_path)


@given('valid subject and back PNG inputs with OCR sidecar text "{text}"')
def step_inputs(context, text: str) -> None:
    context.subject = context.root / "front.png"
    context.back = context.root / "back.png"
    make_png(context.subject, 1800, 1600)
    make_png(context.back, 1800, 1600)
    context.back.with_suffix(".txt").write_text(text, encoding="utf-8")


@given("the web server is started for browser testing")
def step_start_web(context) -> None:
    Handler.pipeline = context.pipeline
    try:
        context.web_server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    except PermissionError as exc:
        context.scenario.skip(f"socket bind not permitted in current environment: {exc}")
        return
    host, port = context.web_server.server_address
    context.web_base_url = f"http://{host}:{port}"
    context.web_thread = threading.Thread(target=context.web_server.serve_forever, daemon=True)
    context.web_thread.start()


@when('I open the browser page "{path}"')
def step_open_browser(context, path: str) -> None:
    with urllib.request.urlopen(context.web_base_url + path, timeout=3) as response:
        context.browser_page = response.read().decode("utf-8", errors="replace")


@then('the page should contain "{text}"')
def step_page_contains(context, text: str) -> None:
    assert text in context.browser_page


@when("I upload fixture files through the web page form")
def step_upload_fixtures(context) -> None:
    project_root = Path(__file__).resolve().parents[4]
    subject = project_root / "tests" / "fixtures" / "front.png"
    back = project_root / "tests" / "fixtures" / "back.png"

    body, boundary = _build_multipart(
        fields={"auto_run": "false"},
        files={
            "subject_file": ("subject.png", subject.read_bytes(), "image/png"),
            "back_file": ("back.png", back.read_bytes(), "image/png"),
        },
    )
    req = urllib.request.Request(
        context.web_base_url + "/upload-web",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        context.upload_response = response.read().decode("utf-8", errors="replace")


@when("I upload a JPEG subject through the web page form")
def step_upload_jpeg_subject(context) -> None:
    subject = context.root / "phone.jpg"
    make_jpeg(subject, 3024, 4032)

    body, boundary = _build_multipart(
        fields={"auto_run": "false"},
        files={
            "subject_file": ("phone.jpg", subject.read_bytes(), "image/jpeg"),
        },
    )
    req = urllib.request.Request(
        context.web_base_url + "/upload-web",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        context.upload_response = response.read().decode("utf-8", errors="replace")


@then("a job should be created from web upload")
def step_job_created(context) -> None:
    jobs = context.pipeline.queue.list_jobs()
    assert len(jobs) >= 1
    assert "Caipture Control Center" in context.upload_response


@then("the central journal should contain web upload actions")
def step_journal_has_actions(context) -> None:
    journal = Path(context.pipeline.config["monitoring"]["runtime_dir"]) / "journal.jsonl"
    assert journal.exists()
    text = journal.read_text(encoding="utf-8")
    assert "http_post" in text
    assert "create_job" in text


@then("the created web job should preserve the JPEG input")
def step_web_job_preserves_jpeg(context) -> None:
    job = context.pipeline.queue.list_jobs()[-1]
    assert job["front_input"].endswith(".jpg")
    job_dir = Path(context.pipeline.config["storage"]["root"]) / "jobs" / job["job_id"]
    assert (job_dir / job["front_input"]).exists()


@when("I create a new processing job")
def step_create(context) -> None:
    created = context.pipeline.create_job(subject_path=str(context.subject), back_path=str(context.back), context_paths=[])
    context.job_id = created["job_id"]


@when("I run the CV, OCR, and metadata workers once")
def step_run_stages(context) -> None:
    context.cv_processed = context.pipeline.run_cv_worker_once()
    context.ocr_processed = context.pipeline.run_ocr_worker_once()
    context.metadata_processed = context.pipeline.run_metadata_worker_once()


@when("I run the CV worker once")
def step_run_cv(context) -> None:
    context.cv_processed = context.pipeline.run_cv_worker_once()


@when("I run the OCR and metadata workers once")
def step_run_ocr_md(context) -> None:
    context.ocr_processed = context.pipeline.run_ocr_worker_once()
    context.metadata_processed = context.pipeline.run_metadata_worker_once()


@when('I approve the review as "{approved_by}"')
def step_approve(context, approved_by: str) -> None:
    context.pipeline.apply_review(context.job_id, approved_by=approved_by)


@when("I run the export worker once")
def step_run_export(context) -> None:
    context.export_processed = context.pipeline.run_export_worker_once()


@then('the job status should be "{status}"')
def step_job_status(context, status: str) -> None:
    assert context.pipeline.queue.fetch_job(context.job_id)["status"] == status


@then("the export image and sidecar should exist")
def step_export_artifacts(context) -> None:
    storage_root = Path(context.pipeline.config["storage"]["root"])
    out_image = storage_root / "jobs" / context.job_id / "exports" / "photo_export.png"
    sidecar = storage_root / "jobs" / context.job_id / "exports" / "photo_export.sidecar.json"
    assert out_image.exists()
    assert sidecar.exists()


@then('the final job status should be "{status}"')
def step_final_status(context, status: str) -> None:
    assert context.pipeline.queue.fetch_job(context.job_id)["status"] == status


@then("no OCR jobs should be processed")
def step_no_ocr(context) -> None:
    assert context.ocr_processed == 0


@then("no metadata jobs should be processed")
def step_no_metadata(context) -> None:
    assert context.metadata_processed == 0

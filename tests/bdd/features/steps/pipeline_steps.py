from __future__ import annotations

import json
import tempfile
from pathlib import Path

from behave import given, then, when

from caipture.pipeline import Pipeline
from tests.test_utils import make_png


def _make_config(root: Path, cv_min_bytes: int) -> Path:
    cfg = {
        "web": {"host": "127.0.0.1", "port": 8080},
        "monitoring": {
            "runtime_dir": str(root / "storage" / "runtime"),
            "llm_gateway_health_url": "http://127.0.0.1:8090/health",
            "refresh_seconds": 1,
        },
        "storage": {"root": str(root / "storage")},
        "upload": {"allowed_image_formats": ["png"], "min_longest_side_px": 1500},
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


@given('valid front and back PNG inputs with OCR sidecar text "{text}"')
def step_inputs(context, text: str) -> None:
    context.front = context.root / "front.png"
    context.back = context.root / "back.png"
    make_png(context.front, 1800, 1600)
    make_png(context.back, 1800, 1600)
    context.back.with_suffix(".txt").write_text(text, encoding="utf-8")


@when("I create a new processing job")
def step_create(context) -> None:
    created = context.pipeline.create_job(str(context.front), str(context.back), [])
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

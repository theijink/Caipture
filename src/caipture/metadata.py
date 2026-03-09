from __future__ import annotations

from typing import Any

from caipture.models import JobStatus, ReviewStatus

ALLOWED_JOB_STATUS = {s.value for s in JobStatus}
ALLOWED_REVIEW_STATUS = {s.value for s in ReviewStatus}
ALLOWED_DATE_PRECISION = {"year", "month", "day", "season", "range", "unknown"}
ALLOWED_SOURCE_TYPES = {
    "back_note",
    "album_caption",
    "context_image",
    "ocr_text",
    "rule_engine",
    "vision_model",
    "llm_inference",
    "manual_entry",
}


def validate_metadata_document(doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    for key in [
        "schema_version",
        "item_id",
        "job_id",
        "created_at",
        "updated_at",
        "status",
        "inputs",
        "derived",
        "historical_metadata",
        "digitization_metadata",
        "review",
    ]:
        if key not in doc:
            errors.append(f"missing top-level field: {key}")

    status = doc.get("status")
    if status not in ALLOWED_JOB_STATUS:
        errors.append("invalid status")

    review = doc.get("review", {})
    if review.get("status") not in ALLOWED_REVIEW_STATUS:
        errors.append("invalid review.status")

    _validate_interpretation_object(doc.get("historical_metadata", {}).get("date"), "historical_metadata.date", errors)
    date_obj = doc.get("historical_metadata", {}).get("date")
    if isinstance(date_obj, dict):
        if date_obj.get("precision") not in ALLOWED_DATE_PRECISION:
            errors.append("historical_metadata.date.precision invalid")

    location = doc.get("historical_metadata", {}).get("location")
    _validate_interpretation_object(location, "historical_metadata.location", errors)

    people = doc.get("historical_metadata", {}).get("people", [])
    if not isinstance(people, list):
        errors.append("historical_metadata.people must be list")

    return errors


def _validate_interpretation_object(obj: Any, name: str, errors: list[str]) -> None:
    if obj is None:
        return
    if not isinstance(obj, dict):
        errors.append(f"{name} must be object")
        return

    confidence = obj.get("confidence")
    if not isinstance(confidence, (float, int)):
        errors.append(f"{name}.confidence must be numeric")
    elif confidence < 0.0 or confidence > 1.0:
        errors.append(f"{name}.confidence out of range")

    sources = obj.get("sources")
    if not isinstance(sources, list):
        errors.append(f"{name}.sources must be list")
        return

    for source in sources:
        if not isinstance(source, dict):
            errors.append(f"{name}.sources entries must be object")
            continue
        source_type = source.get("source_type")
        if source_type not in ALLOWED_SOURCE_TYPES:
            errors.append(f"{name}.sources source_type invalid")

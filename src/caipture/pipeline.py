from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from caipture.config import load_config
from caipture.llm_gateway import LlmGateway
from caipture.metadata import validate_metadata_document
from caipture.models import JobStatus, ReviewStatus
from caipture.queue import JobQueue
from caipture.session_metrics import SessionMetrics
from caipture.store import Storage
from caipture.utils import image_dimensions, read_json, sha256_file, utc_now_iso, write_json


class Pipeline:
    def __init__(self, config_path: str | Path | None = None) -> None:
        self.config = load_config(config_path)
        self.storage = Storage(Path(self.config["storage"]["root"]))
        self.storage.init_layout()
        self.queue = JobQueue(Path(self.config["queue"]["db_path"]))
        self.llm = LlmGateway(enabled=bool(self.config["metadata"].get("enable_llm_gateway", False)))
        runtime_dir = Path(self.config.get("monitoring", {}).get("runtime_dir", Path(self.config["storage"]["root"]) / "runtime"))
        self.metrics = SessionMetrics(runtime_dir / "session_metrics.json")

    def create_job(self, front_path: str, back_path: str, context_paths: list[str] | None = None) -> dict[str, Any]:
        context_paths = context_paths or []
        job_id = f"job_{utc_now_iso().replace('-', '').replace(':', '').replace('T', '_').replace('Z', '')}_{len(self.queue.list_jobs())+1:04d}"
        item_id = f"item_{job_id.split('_', 1)[1]}"

        front_src = Path(front_path)
        back_src = Path(back_path)
        if not front_src.exists() or not back_src.exists():
            raise FileNotFoundError("front_path and back_path must exist")

        self._validate_upload_file(front_src)
        self._validate_upload_file(back_src)
        for context in context_paths:
            self._validate_upload_file(Path(context))

        self.storage.create_job_dirs(job_id)
        front_ref = self.storage.ingest_file(front_src, job_id, f"front{front_src.suffix.lower()}")
        back_ref = self.storage.ingest_file(back_src, job_id, f"back{back_src.suffix.lower()}")

        context_refs: list[str] = []
        for idx, context_path in enumerate(context_paths, start=1):
            src = Path(context_path)
            ref = self.storage.ingest_file(src, job_id, f"context_{idx:03d}{src.suffix.lower()}")
            context_refs.append(ref.path)

        self.queue.create_job(
            {
                "job_id": job_id,
                "item_id": item_id,
                "front_input": front_ref.path,
                "back_input": back_ref.path,
                "context_inputs": context_refs,
            }
        )
        self.queue.set_status(job_id, JobStatus.QUEUED)
        self.queue.add_event(job_id, "upload", "queued", {})
        return {"job_id": job_id, "item_id": item_id}

    def run_cv_worker_once(self) -> int:
        jobs = self.queue.select_for_cv()
        processed = 0
        for job in jobs:
            processed += 1
            job_id = job["job_id"]
            self.queue.set_status(job_id, JobStatus.PROCESSING)
            self.queue.add_event(job_id, "cv", "started", {})
            try:
                front_abs = self.storage.job_dir(job_id) / job["front_input"]
                issues = self._cv_validate(front_abs)
                derived_dir = self.storage.job_dir(job_id) / "derived"
                if issues:
                    report_path = derived_dir / "validation_report.json"
                    write_json(report_path, {"issues": issues})
                    self.queue.set_status(job_id, JobStatus.VALIDATION_FAILED, "validation_failed", " ;".join(issues))
                    self.queue.update_flags(job_id, cv_done=True)
                    self.queue.add_event(job_id, "cv", "failed", {"issues": issues})
                    continue

                rectified = derived_dir / "front_rectified.png"
                cropped = derived_dir / "front_cropped.png"
                shutil.copy2(front_abs, rectified)
                shutil.copy2(front_abs, cropped)
                write_json(
                    derived_dir / "validation_report.json",
                    {"issues": [], "status": "ok", "generated": ["derived/front_cropped.png", "derived/front_rectified.png"]},
                )
                self.queue.update_flags(job_id, cv_done=True)
                self.queue.add_event(job_id, "cv", "succeeded", {"rectified": "derived/front_rectified.png"})
                self.metrics.increment_stage("cv")
            except Exception as exc:  # pragma: no cover
                self.queue.set_status(job_id, JobStatus.FAILED, "cv_error", str(exc))
                self.queue.add_event(job_id, "cv", "failed", {"error": str(exc)})
        return processed

    def run_ocr_worker_once(self) -> int:
        jobs = self.queue.select_for_ocr()
        processed = 0
        for job in jobs:
            processed += 1
            job_id = job["job_id"]
            self.queue.add_event(job_id, "ocr", "started", {})
            try:
                derived_dir = self.storage.job_dir(job_id) / "derived"
                text_parts = []
                for rel in [job["back_input"], *job["context_inputs"]]:
                    p = self.storage.job_dir(job_id) / rel
                    text_parts.append(self._extract_ocr_text(p))

                back_text = text_parts[0] if text_parts else ""
                context_text = "\n".join(text_parts[1:])
                (derived_dir / "back_ocr.txt").write_text(back_text, encoding="utf-8")
                (derived_dir / "context_ocr.txt").write_text(context_text, encoding="utf-8")
                write_json(
                    derived_dir / "ocr_report.json",
                    {
                        "back_confidence": self._confidence_for_text(back_text),
                        "context_confidence": self._confidence_for_text(context_text),
                    },
                )
                self.queue.update_flags(job_id, ocr_done=True)
                self.queue.add_event(job_id, "ocr", "succeeded", {})
                self.metrics.increment_stage("ocr")
            except Exception as exc:  # pragma: no cover
                self.queue.set_status(job_id, JobStatus.FAILED, "ocr_error", str(exc))
                self.queue.add_event(job_id, "ocr", "failed", {"error": str(exc)})
        return processed

    def run_metadata_worker_once(self) -> int:
        jobs = self.queue.select_for_metadata()
        processed = 0
        for job in jobs:
            processed += 1
            job_id = job["job_id"]
            self.queue.add_event(job_id, "metadata", "started", {})
            try:
                job_dir = self.storage.job_dir(job_id)
                back_text = (job_dir / "derived" / "back_ocr.txt").read_text(encoding="utf-8") if (job_dir / "derived" / "back_ocr.txt").exists() else ""
                context_text = (job_dir / "derived" / "context_ocr.txt").read_text(encoding="utf-8") if (job_dir / "derived" / "context_ocr.txt").exists() else ""
                merged_text = "\n".join([back_text, context_text]).strip()

                date_obj = self._infer_date(merged_text)
                location_obj = self._infer_location(merged_text)
                llm_summary = self.llm.summarize_context(merged_text)
                self.metrics.increment("llm_requests_total")
                if bool(llm_summary.get("used_provider", False)):
                    self.metrics.increment("llm_enabled_requests")

                review_threshold = float(self.config["review"]["auto_approve_min_confidence"])
                low_confidence = []
                for key, obj in [("date", date_obj), ("location", location_obj)]:
                    if obj and float(obj.get("confidence", 0.0)) < review_threshold:
                        low_confidence.append(f"{key}_confidence_below_threshold")

                review_required = bool(low_confidence)
                now = utc_now_iso()
                metadata_doc = {
                    "schema_version": "0.2.0",
                    "item_id": job["item_id"],
                    "job_id": job_id,
                    "created_at": job["created_at"],
                    "updated_at": now,
                    "status": JobStatus.REVIEW_REQUIRED.value if review_required else JobStatus.COMPLETED.value,
                    "inputs": {
                        "front_image": self._file_ref_dict(job_dir / job["front_input"], job["front_input"]),
                        "back_image": self._file_ref_dict(job_dir / job["back_input"], job["back_input"]),
                        "context_images": [self._file_ref_dict(job_dir / c, c) for c in job["context_inputs"]],
                    },
                    "derived": {
                        "front_rectified": "derived/front_rectified.png",
                        "front_cropped": "derived/front_cropped.png",
                        "back_ocr_text": "derived/back_ocr.txt",
                        "context_ocr_texts": ["derived/context_ocr.txt"],
                        "validation_report": "derived/validation_report.json",
                        "ocr_report": "derived/ocr_report.json",
                    },
                    "historical_metadata": {
                        "date": date_obj,
                        "location": location_obj,
                        "people": [],
                        "description": {
                            "text": llm_summary["description"],
                            "confidence": llm_summary["confidence"],
                            "sources": [
                                {
                                    "source_type": "llm_inference",
                                    "source_ref": "llm-gateway",
                                }
                            ],
                        },
                    },
                    "digitization_metadata": {
                        "digitized_at": now,
                        "pipeline_version": self.config["metadata"]["pipeline_version"],
                        "config_version": self.config["metadata"]["config_version"],
                        "tools": {
                            "ocr": self.config["ocr"]["engine"],
                            "cv": self.config["cv"]["engine"],
                        },
                    },
                    "review": {
                        "required": review_required,
                        "reasons": low_confidence,
                        "status": ReviewStatus.PENDING.value if review_required else ReviewStatus.NOT_REQUIRED.value,
                        "approved_by": None,
                        "approved_at": None,
                        "changes": [],
                    },
                    "export_mapping": {},
                    "revisions": [],
                }
                errors = validate_metadata_document(metadata_doc)
                if errors:
                    raise ValueError("metadata schema validation failed: " + " | ".join(errors))

                write_json(job_dir / "metadata" / "photo_item.json", metadata_doc)
                self.queue.update_flags(job_id, metadata_done=True)
                self.queue.set_status(job_id, JobStatus.REVIEW_REQUIRED if review_required else JobStatus.COMPLETED)
                if not review_required:
                    self.queue.update_flags(job_id, review_done=True)
                self.queue.add_event(job_id, "metadata", "succeeded", {"review_required": review_required})
                self.metrics.increment_stage("metadata")
            except Exception as exc:  # pragma: no cover
                self.queue.set_status(job_id, JobStatus.FAILED, "metadata_error", str(exc))
                self.queue.add_event(job_id, "metadata", "failed", {"error": str(exc)})
        return processed

    def apply_review(self, job_id: str, approved_by: str, notes: str = "") -> None:
        job_dir = self.storage.job_dir(job_id)
        metadata_path = job_dir / "metadata" / "photo_item.json"
        doc = read_json(metadata_path)
        doc["review"]["status"] = ReviewStatus.APPROVED.value
        doc["review"]["approved_by"] = approved_by
        doc["review"]["approved_at"] = utc_now_iso()
        doc["review"]["notes"] = notes
        doc["review"]["required"] = False
        doc["review"]["reasons"] = []
        doc["updated_at"] = utc_now_iso()
        doc["status"] = JobStatus.COMPLETED.value
        write_json(metadata_path, doc)

        self.queue.update_flags(job_id, review_done=True)
        self.queue.set_status(job_id, JobStatus.COMPLETED)
        self.queue.add_event(job_id, "review", "approved", {"approved_by": approved_by})

    def run_export_worker_once(self) -> int:
        jobs = self.queue.select_for_export()
        processed = 0
        for job in jobs:
            processed += 1
            job_id = job["job_id"]
            self.queue.add_event(job_id, "export", "started", {})
            try:
                job_dir = self.storage.job_dir(job_id)
                metadata_path = job_dir / "metadata" / "photo_item.json"
                doc = read_json(metadata_path)

                rectified = job_dir / "derived" / "front_rectified.png"
                out_image = job_dir / "exports" / "photo_export.png"
                shutil.copy2(rectified, out_image)

                mapping = {
                    "exif": {
                        "DateTimeDigitized": doc["digitization_metadata"]["digitized_at"],
                    },
                    "iptc": {
                        "CaptionAbstract": doc.get("historical_metadata", {}).get("description", {}).get("text", ""),
                    },
                    "xmp": {
                        "caipture:ItemId": doc["item_id"],
                        "caipture:JobId": doc["job_id"],
                    },
                    "exported_at": utc_now_iso(),
                    "export_profile": self.config["export"]["profile"],
                }
                doc["export_mapping"] = mapping
                doc["updated_at"] = utc_now_iso()
                write_json(metadata_path, doc)
                write_json(job_dir / "exports" / "photo_export.sidecar.json", doc)

                self.queue.update_flags(job_id, export_done=True)
                self.queue.set_status(job_id, JobStatus.COMPLETED)
                self.queue.add_event(job_id, "export", "succeeded", {"path": "exports/photo_export.png"})
                self.metrics.increment_stage("export")
            except Exception as exc:  # pragma: no cover
                self.queue.set_status(job_id, JobStatus.FAILED, "export_error", str(exc))
                self.queue.add_event(job_id, "export", "failed", {"error": str(exc)})
        return processed

    def run_all_once(self) -> dict[str, int]:
        return {
            "cv": self.run_cv_worker_once(),
            "ocr": self.run_ocr_worker_once(),
            "metadata": self.run_metadata_worker_once(),
            "export": self.run_export_worker_once(),
        }

    def _validate_upload_file(self, path: Path) -> None:
        allowed = {x.lower() for x in self.config["upload"]["allowed_image_formats"]}
        suffix = path.suffix.lower().lstrip(".")
        if suffix not in allowed:
            raise ValueError(f"Unsupported image format: {path.suffix}")

        dims = image_dimensions(path)
        if dims is None:
            raise ValueError(f"Unsupported or unreadable image dimensions for {path}")
        longest = max(dims)
        min_px = int(self.config["upload"]["min_longest_side_px"])
        if longest < min_px:
            raise ValueError(f"Image too small ({longest}px), minimum is {min_px}px")

    def _cv_validate(self, front_image: Path) -> list[str]:
        issues: list[str] = []
        dims = image_dimensions(front_image)
        if dims is None:
            issues.append("unreadable_dimensions")
            return issues

        min_side = int(self.config["cv"].get("min_short_side_px", 900))
        if min(dims) < min_side:
            issues.append("short_side_below_threshold")

        if front_image.stat().st_size < int(self.config["cv"].get("min_bytes", 1024)):
            issues.append("file_too_small")

        return issues

    def _extract_ocr_text(self, path: Path) -> str:
        # PoC deterministic OCR surrogate: derive text from filename and optional sidecar .txt.
        sidecar = path.with_suffix(".txt")
        if sidecar.exists():
            return sidecar.read_text(encoding="utf-8")

        base = path.stem.replace("_", " ").replace("-", " ")
        return base.strip()

    def _confidence_for_text(self, text: str) -> float:
        if not text.strip():
            return 0.2
        if len(text.split()) < 2:
            return 0.45
        return 0.75

    def _infer_date(self, text: str) -> dict[str, Any] | None:
        year_match = re.search(r"\b(18\d{2}|19\d{2}|20\d{2})\b", text)
        if not year_match:
            return None
        year = year_match.group(1)
        return {
            "raw_text": year,
            "from": f"{year}-01-01",
            "to": f"{year}-12-31",
            "precision": "year",
            "confidence": 0.72,
            "sources": [
                {
                    "source_type": "ocr_text",
                    "source_ref": "derived/back_ocr.txt",
                    "excerpt": year,
                }
            ],
        }

    def _infer_location(self, text: str) -> dict[str, Any] | None:
        locations = self.config["metadata"].get("location_dictionary", {})
        text_lower = text.lower()
        for key, normalized in locations.items():
            if key.lower() in text_lower:
                return {
                    "raw_text": key,
                    "normalized": normalized,
                    "confidence": 0.7,
                    "sources": [
                        {
                            "source_type": "ocr_text",
                            "source_ref": "derived/back_ocr.txt",
                            "excerpt": key,
                        }
                    ],
                }
        return {
            "raw_text": "",
            "normalized": {"name": ""},
            "confidence": 0.35,
            "sources": [
                {
                    "source_type": "rule_engine",
                    "source_ref": "metadata_worker",
                }
            ],
        }

    def _file_ref_dict(self, abs_path: Path, rel_path: str) -> dict[str, Any]:
        return {
            "path": rel_path,
            "sha256": sha256_file(abs_path),
            "bytes": abs_path.stat().st_size,
        }

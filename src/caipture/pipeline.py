from __future__ import annotations

import re
import shutil
import subprocess
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

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - optional runtime dependency
    cv2 = None
    np = None


class Pipeline:
    def __init__(self, config_path: str | Path | None = None) -> None:
        self.config = load_config(config_path)
        self.storage = Storage(Path(self.config["storage"]["root"]))
        self.storage.init_layout()
        self.queue = JobQueue(Path(self.config["queue"]["db_path"]))
        self.llm = LlmGateway(enabled=bool(self.config["metadata"].get("enable_llm_gateway", False)))
        runtime_dir = Path(self.config.get("monitoring", {}).get("runtime_dir", Path(self.config["storage"]["root"]) / "runtime"))
        self.metrics = SessionMetrics(runtime_dir / "session_metrics.json")

    def create_job(
        self,
        subject_path: str,
        context_paths: list[str] | None = None,
        back_path: str | None = None,
        manual_context: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        context_paths = context_paths or []
        manual_context = manual_context or {}
        job_id = f"job_{utc_now_iso().replace('-', '').replace(':', '').replace('T', '_').replace('Z', '')}_{len(self.queue.list_jobs())+1:04d}"
        item_id = f"item_{job_id.split('_', 1)[1]}"

        front_src = Path(subject_path)
        if not front_src.exists():
            raise FileNotFoundError("subject_path must exist")

        self._validate_upload_file(front_src)
        back_src: Path | None = None
        if back_path:
            back_src = Path(back_path)
            if not back_src.exists():
                raise FileNotFoundError("back_path must exist when provided")
            self._validate_upload_file(back_src)
        for context in context_paths:
            self._validate_upload_file(Path(context))

        self.storage.create_job_dirs(job_id)
        front_ref = self.storage.ingest_file(front_src, job_id, f"front{front_src.suffix.lower()}")
        back_rel = ""
        if back_src is not None:
            back_ref = self.storage.ingest_file(back_src, job_id, f"back{back_src.suffix.lower()}")
            back_rel = back_ref.path

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
                    "back_input": back_rel,
                    "context_inputs": context_refs,
                    "manual_context": manual_context,
                }
            )
        self.queue.set_status(job_id, JobStatus.QUEUED)
        self.queue.add_event(job_id, "upload", "queued", {})
        write_json(self.storage.job_dir(job_id) / "metadata" / "manual_context.json", manual_context)
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
                self._run_cv_transform(front_abs, cropped, rectified)
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
                text_parts: list[str] = []
                confs: list[float] = []
                ocr_refs: list[str] = []
                ocr_inputs = []
                if job["back_input"]:
                    ocr_inputs.append(job["back_input"])
                ocr_inputs.extend(job["context_inputs"])
                for idx, rel in enumerate(ocr_inputs):
                    p = self.storage.job_dir(job_id) / rel
                    text, conf = self._extract_ocr_text(p)
                    text_parts.append(text)
                    confs.append(conf)
                    if idx == 0:
                        out_ref = "derived/back_ocr.txt"
                        (derived_dir / "back_ocr.txt").write_text(text, encoding="utf-8")
                    else:
                        out_ref = f"derived/context_ocr_{idx:03d}.txt"
                        (derived_dir / f"context_ocr_{idx:03d}.txt").write_text(text, encoding="utf-8")
                    ocr_refs.append(out_ref)

                back_text = text_parts[0] if (text_parts and job["back_input"]) else ""
                context_text = "\n".join(text_parts[1:] if job["back_input"] else text_parts)
                (derived_dir / "context_ocr.txt").write_text(context_text, encoding="utf-8")
                write_json(
                    derived_dir / "ocr_report.json",
                    {
                        "engine": self.config["ocr"].get("engine", "ocr"),
                        "tesseract_available": shutil.which("tesseract") is not None,
                        "psm_candidates": self.config["ocr"].get("psm_candidates", [6, 11, 12]),
                        "preprocessing_enabled": bool(self.config["ocr"].get("enable_preprocessing", True)),
                        "back_confidence": confs[0] if confs else self._confidence_for_text(back_text),
                        "context_confidence": (sum(confs[1:]) / len(confs[1:])) if len(confs) > 1 else self._confidence_for_text(context_text),
                        "ocr_artifacts": ocr_refs,
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
                manual_context = read_json(job_dir / "metadata" / "manual_context.json") if (job_dir / "metadata" / "manual_context.json").exists() else job.get("manual_context", {})
                context_parts = []
                for i in range(1, 32):
                    p = job_dir / "derived" / f"context_ocr_{i:03d}.txt"
                    if not p.exists():
                        break
                    context_parts.append(p.read_text(encoding="utf-8"))
                merged_text = "\n".join(
                    [back_text, context_text, manual_context.get("date", ""), manual_context.get("location", ""), manual_context.get("comment", "")]
                ).strip()

                date_obj = self._infer_date(merged_text)
                location_obj = self._infer_location(merged_text)
                people_obj = self._infer_people(merged_text)
                llm_summary = self.llm.summarize_context(merged_text)
                if manual_context.get("date"):
                    date_obj = self._manual_date(manual_context["date"])
                if manual_context.get("location"):
                    location_obj = self._manual_location(manual_context["location"])
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
                        "subject_image": self._file_ref_dict(job_dir / job["front_input"], job["front_input"]),
                        "back_image": self._file_ref_dict(job_dir / job["back_input"], job["back_input"]) if job["back_input"] else None,
                        "context_images": [self._file_ref_dict(job_dir / c, c) for c in job["context_inputs"]],
                    },
                    "derived": {
                        "front_rectified": "derived/front_rectified.png",
                        "front_cropped": "derived/front_cropped.png",
                        "back_ocr_text": "derived/back_ocr.txt",
                        "context_ocr_texts": [f"derived/context_ocr_{i:03d}.txt" for i in range(1, len(context_parts) + 1)] or ["derived/context_ocr.txt"],
                        "validation_report": "derived/validation_report.json",
                        "ocr_report": "derived/ocr_report.json",
                    },
                    "historical_metadata": {
                        "date": date_obj,
                        "location": location_obj,
                        "people": people_obj,
                        "source_text": {
                            "back_ocr_text": back_text,
                            "context_ocr_text": context_text,
                            "context_ocr_texts": context_parts,
                            "manual_context": manual_context,
                        },
                        "event": self._infer_event(merged_text),
                        "description": {
                            "text": manual_context.get("comment") or llm_summary["description"] or self._infer_description(merged_text, people_obj, location_obj),
                            "confidence": llm_summary["confidence"] if llm_summary["description"] else 0.6,
                            "sources": [
                                {
                                    "source_type": "manual_entry" if manual_context.get("comment") else "llm_inference",
                                    "source_ref": "manual_context" if manual_context.get("comment") else "llm-gateway",
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
        self._update_description_memory(doc)

        self.queue.update_flags(job_id, review_done=True)
        self.queue.set_status(job_id, JobStatus.COMPLETED)
        self.queue.add_event(job_id, "review", "approved", {"approved_by": approved_by})

    def delete_job(self, job_id: str) -> bool:
        job_dir = self.storage.job_dir(job_id)
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
        return self.queue.delete_job(job_id)

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
                        "DateTimeOriginal": doc.get("historical_metadata", {}).get("date", {}).get("from", ""),
                    },
                    "iptc": {
                        "CaptionAbstract": doc.get("historical_metadata", {}).get("description", {}).get("text", ""),
                        "City": doc.get("historical_metadata", {}).get("location", {}).get("normalized", {}).get("name", ""),
                    },
                    "xmp": {
                        "caipture:ItemId": doc["item_id"],
                        "caipture:JobId": doc["job_id"],
                    },
                    "exported_at": utc_now_iso(),
                    "export_profile": self.config["export"]["profile"],
                }
                comment = self._build_export_comment(doc)
                self._apply_export_metadata(out_image, comment)
                self._set_export_timestamp_from_metadata(out_image, doc)
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

    def _extract_ocr_text(self, path: Path) -> tuple[str, float]:
        # Prefer deterministic sidecar for tests/debug, then fallback to OCR engine.
        sidecar = path.with_suffix(".txt")
        if sidecar.exists():
            text = sidecar.read_text(encoding="utf-8")
            return text, self._confidence_for_text(text)

        lang = str(self.config["ocr"].get("language", "eng"))
        psm_candidates = self.config["ocr"].get("psm_candidates", [6, 11, 12])
        preprocessed_paths = self._build_ocr_preprocess_variants(path)

        best_text = ""
        best_conf = 0.0
        best_score = -1.0

        for variant in preprocessed_paths:
            for psm in psm_candidates:
                text, conf = self._run_tesseract(variant, lang=lang, psm=int(psm))
                score = conf + min(len(text.split()) / 30.0, 0.3)
                if score > best_score:
                    best_score = score
                    best_text = text
                    best_conf = conf

        for p in preprocessed_paths:
            if p != path and p.exists():
                p.unlink(missing_ok=True)

        if not best_text:
            base = path.stem.replace("_", " ").replace("-", " ")
            best_text = base.strip()
            best_conf = self._confidence_for_text(best_text)
        return best_text, best_conf

    def _run_tesseract(self, path: Path, lang: str, psm: int) -> tuple[str, float]:
        try:
            text = subprocess.run(
                ["tesseract", str(path), "stdout", "-l", lang, "--psm", str(psm)],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        except Exception:
            return "", 0.0

        conf = self._confidence_for_text(text)
        try:
            tsv = subprocess.run(
                ["tesseract", str(path), "stdout", "-l", lang, "--psm", str(psm), "tsv"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            vals: list[float] = []
            for line in tsv.splitlines()[1:]:
                parts = line.split("\t")
                if len(parts) < 11:
                    continue
                try:
                    c = float(parts[10])
                except ValueError:
                    continue
                if c >= 0.0:
                    vals.append(c / 100.0)
            if vals:
                conf = max(0.0, min(1.0, sum(vals) / len(vals)))
        except Exception:
            pass
        return text, conf

    def _build_ocr_preprocess_variants(self, path: Path) -> list[Path]:
        variants = [path]
        if not bool(self.config["ocr"].get("enable_preprocessing", True)):
            return variants
        tmp_dir = path.parent
        alt1 = tmp_dir / f"{path.stem}_ocr_gray{path.suffix}"
        alt2 = tmp_dir / f"{path.stem}_ocr_thresh{path.suffix}"
        cmds = [
            ["magick", str(path), "-colorspace", "Gray", "-contrast-stretch", "0", "-sharpen", "0x1", str(alt1)],
            ["magick", str(path), "-colorspace", "Gray", "-median", "1", "-threshold", "55%", str(alt2)],
        ]
        for cmd, out in zip(cmds, [alt1, alt2]):
            try:
                subprocess.run(cmd, capture_output=True, text=True, check=True)
                if out.exists():
                    variants.append(out)
            except Exception:
                out.unlink(missing_ok=True)
        return variants

    def _confidence_for_text(self, text: str) -> float:
        if not text.strip():
            return 0.2
        if len(text.split()) < 2:
            return 0.45
        return 0.75

    def _infer_date(self, text: str) -> dict[str, Any] | None:
        full_date = re.search(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b", text)
        if full_date:
            y, m, d = full_date.groups()
            iso = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
            return {
                "raw_text": full_date.group(0),
                "from": iso,
                "to": iso,
                "precision": "day",
                "confidence": 0.82,
                "sources": [{"source_type": "ocr_text", "source_ref": "derived/back_ocr.txt", "excerpt": full_date.group(0)}],
            }
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

    def _infer_people(self, text: str) -> list[dict[str, Any]]:
        people: list[dict[str, Any]] = []
        for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text):
            name = match.group(1).strip()
            if name.lower() in {"Summer"}:
                continue
            people.append(
                {
                    "name": name,
                    "role": "possible_subject",
                    "confidence": 0.55,
                    "sources": [
                        {
                            "source_type": "ocr_text",
                            "source_ref": "derived/back_ocr.txt",
                            "excerpt": name,
                        }
                    ],
                }
            )
        # Deduplicate by name.
        seen = set()
        uniq = []
        for p in people:
            n = p["name"]
            if n in seen:
                continue
            seen.add(n)
            uniq.append(p)
        return uniq[:10]

    def _infer_description(self, text: str, people: list[dict[str, Any]], location: dict[str, Any] | None) -> str:
        bits = []
        if people:
            bits.append("People: " + ", ".join([p["name"] for p in people[:3]]))
        loc = (location or {}).get("normalized", {}).get("name", "")
        if loc:
            bits.append("Location: " + loc)
        if text:
            bits.append("Context: " + " ".join(text.split()[:25]))
        return " | ".join(bits) if bits else "Historical photograph."

    def _infer_event(self, text: str) -> dict[str, Any] | None:
        keywords = {
            "wedding": "Wedding",
            "birthday": "Birthday",
            "vacation": "Vacation",
            "school": "School",
            "graduation": "Graduation",
            "christmas": "Christmas",
        }
        low = text.lower()
        for k, label in keywords.items():
            if k in low:
                return {
                    "name": label,
                    "confidence": 0.65,
                    "sources": [{"source_type": "ocr_text", "source_ref": "derived/context_ocr.txt", "excerpt": k}],
                }
        return None

    def _manual_date(self, raw: str) -> dict[str, Any]:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", raw)
        if m:
            iso = m.group(1)
            return {
                "raw_text": raw,
                "from": iso,
                "to": iso,
                "precision": "day",
                "confidence": 1.0,
                "sources": [{"source_type": "manual_entry", "source_ref": "manual_context", "excerpt": raw}],
            }
        year = re.search(r"(18\d{2}|19\d{2}|20\d{2})", raw)
        y = year.group(1) if year else "1900"
        return {
            "raw_text": raw,
            "from": f"{y}-01-01",
            "to": f"{y}-12-31",
            "precision": "year",
            "confidence": 1.0,
            "sources": [{"source_type": "manual_entry", "source_ref": "manual_context", "excerpt": raw}],
        }

    def _manual_location(self, raw: str) -> dict[str, Any]:
        return {
            "raw_text": raw,
            "normalized": {"name": raw},
            "confidence": 1.0,
            "sources": [{"source_type": "manual_entry", "source_ref": "manual_context", "excerpt": raw}],
        }

    def _description_memory_path(self) -> Path:
        runtime_dir = Path(self.config.get("monitoring", {}).get("runtime_dir", Path(self.config["storage"]["root"]) / "runtime"))
        runtime_dir.mkdir(parents=True, exist_ok=True)
        return runtime_dir / "description_memory.json"

    def _update_description_memory(self, doc: dict[str, Any]) -> None:
        desc = doc.get("historical_metadata", {}).get("description", {}).get("text", "").strip()
        loc = doc.get("historical_metadata", {}).get("location", {}).get("normalized", {}).get("name", "").strip()
        if not desc:
            return
        path = self._description_memory_path()
        mem = read_json(path) if path.exists() else {"items": []}
        mem.setdefault("items", []).append({"location": loc, "description": desc, "updated_at": utc_now_iso()})
        mem["items"] = mem["items"][-200:]
        write_json(path, mem)

    def _file_ref_dict(self, abs_path: Path, rel_path: str) -> dict[str, Any]:
        return {
            "path": rel_path,
            "sha256": sha256_file(abs_path),
            "bytes": abs_path.stat().st_size,
        }

    def _run_cv_transform(self, input_path: Path, cropped_path: Path, rectified_path: Path) -> None:
        if cv2 is not None and np is not None:
            if self._run_cv_transform_opencv(input_path, cropped_path, rectified_path):
                return

        fuzz = str(self.config["cv"].get("trim_fuzz_percent", 10))
        target = str(self.config["cv"].get("target_size", "1600x1200"))
        cmd_crop = [
            "magick",
            str(input_path),
            "-auto-orient",
            "-fuzz",
            f"{fuzz}%",
            "-trim",
            "+repage",
            str(cropped_path),
        ]
        cmd_rect = [
            "magick",
            str(cropped_path),
            "-resize",
            f"{target}>",
            str(rectified_path),
        ]
        try:
            subprocess.run(cmd_crop, check=True, capture_output=True, text=True)
            subprocess.run(cmd_rect, check=True, capture_output=True, text=True)
        except Exception:
            # Fallback keeps pipeline running but still produces artifacts.
            shutil.copy2(input_path, cropped_path)
            shutil.copy2(input_path, rectified_path)

    def _run_cv_transform_opencv(self, input_path: Path, cropped_path: Path, rectified_path: Path) -> bool:
        try:
            image = cv2.imread(str(input_path))
            if image is None:
                return False
            original = image.copy()
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blur, 40, 120)
            edges = cv2.dilate(edges, None, iterations=2)
            edges = cv2.erode(edges, None, iterations=1)

            contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            contours = sorted(contours, key=cv2.contourArea, reverse=True)
            best_quad = None
            img_area = image.shape[0] * image.shape[1]
            for contour in contours[:20]:
                peri = cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
                area = cv2.contourArea(approx)
                if len(approx) == 4 and area > img_area * 0.1:
                    best_quad = approx.reshape(4, 2).astype("float32")
                    break

            if best_quad is not None:
                rect = self._order_points(best_quad)
                warped = self._four_point_transform(original, rect)
                cv2.imwrite(str(cropped_path), warped)
                rectified = self._resize_for_target(warped)
                cv2.imwrite(str(rectified_path), rectified)
                return True

            # Fallback to largest contour bounding box crop.
            if contours:
                x, y, w, h = cv2.boundingRect(contours[0])
                crop = original[y : y + h, x : x + w]
                cv2.imwrite(str(cropped_path), crop)
                rectified = self._resize_for_target(crop)
                cv2.imwrite(str(rectified_path), rectified)
                return True
            return False
        except Exception:
            return False

    def _resize_for_target(self, image: Any) -> Any:
        target = str(self.config["cv"].get("target_size", "1600x1200"))
        tw, th = 1600, 1200
        try:
            tw_s, th_s = target.lower().split("x", 1)
            tw, th = int(tw_s), int(th_s)
        except Exception:
            pass
        h, w = image.shape[:2]
        scale = min(tw / max(w, 1), th / max(h, 1), 1.0)
        new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
        return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

    def _order_points(self, pts: Any) -> Any:
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        return rect

    def _four_point_transform(self, image: Any, rect: Any) -> Any:
        (tl, tr, br, bl) = rect
        width_a = np.linalg.norm(br - bl)
        width_b = np.linalg.norm(tr - tl)
        max_width = int(max(width_a, width_b))
        height_a = np.linalg.norm(tr - br)
        height_b = np.linalg.norm(tl - bl)
        max_height = int(max(height_a, height_b))

        dst = np.array(
            [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
            dtype="float32",
        )
        m = cv2.getPerspectiveTransform(rect, dst)
        return cv2.warpPerspective(image, m, (max_width, max_height))

    def _build_export_comment(self, doc: dict[str, Any]) -> str:
        hist = doc.get("historical_metadata", {})
        parts = []
        date_from = hist.get("date", {}).get("from")
        if date_from:
            parts.append(f"date={date_from}")
        loc = hist.get("location", {}).get("normalized", {}).get("name", "")
        if loc:
            parts.append(f"location={loc}")
        desc = hist.get("description", {}).get("text", "")
        if desc:
            parts.append(f"description={desc}")
        people = [p.get("name", "") for p in hist.get("people", []) if p.get("name")]
        if people:
            parts.append("people=" + ", ".join(people))
        return " | ".join(parts)

    def _apply_export_metadata(self, image_path: Path, comment: str) -> None:
        if not comment:
            return
        try:
            tmp = image_path.with_name(image_path.stem + "_meta" + image_path.suffix)
            subprocess.run(
                ["magick", str(image_path), "-set", "comment", comment, str(tmp)],
                check=True,
                capture_output=True,
                text=True,
            )
            tmp.replace(image_path)
        except Exception:
            return

    def _set_export_timestamp_from_metadata(self, image_path: Path, doc: dict[str, Any]) -> None:
        raw = doc.get("historical_metadata", {}).get("date", {}).get("from")
        if not raw:
            return
        try:
            from datetime import datetime

            dt = datetime.fromisoformat(raw)
            ts = dt.timestamp()
            image_path.touch(exist_ok=True)
            image_path.chmod(0o644)
            import os

            os.utime(image_path, (ts, ts))
        except Exception:
            return

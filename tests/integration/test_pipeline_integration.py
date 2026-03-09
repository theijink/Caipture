from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from caipture.pipeline import Pipeline
from tests.test_utils import make_png


class PipelineIntegrationTests(unittest.TestCase):
    def _make_config(self, root: Path, cv_min_bytes: int = 100) -> Path:
        cfg = {
            "storage": {"root": str(root / "storage")},
            "upload": {"allowed_image_formats": ["png"], "min_longest_side_px": 1500},
            "cv": {"engine": "cv", "min_short_side_px": 900, "min_bytes": cv_min_bytes},
            "ocr": {"engine": "ocr", "language": "eng"},
            "metadata": {
                "pipeline_version": "0.2.0",
                "config_version": "itest",
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

    def test_end_to_end_with_review_and_export(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg_path = self._make_config(root, cv_min_bytes=10)

            front = root / "front.png"
            back = root / "back.png"
            make_png(front, 1800, 1600)
            make_png(back, 1800, 1600)
            back.with_suffix(".txt").write_text("Summer 1934 Enschede family", encoding="utf-8")

            pipeline = Pipeline(cfg_path)
            created = pipeline.create_job(str(front), str(back), [])
            job_id = created["job_id"]

            self.assertEqual(pipeline.run_cv_worker_once(), 1)
            self.assertEqual(pipeline.run_ocr_worker_once(), 1)
            self.assertEqual(pipeline.run_metadata_worker_once(), 1)

            job = pipeline.queue.fetch_job(job_id)
            self.assertIsNotNone(job)
            self.assertEqual(job["status"], "review_required")

            metadata_path = Path(pipeline.config["storage"]["root"]) / "jobs" / job_id / "metadata" / "photo_item.json"
            doc = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(doc["historical_metadata"]["date"]["precision"], "year")
            self.assertEqual(doc["review"]["status"], "pending")

            pipeline.apply_review(job_id, approved_by="tester", notes="looks correct")
            self.assertEqual(pipeline.run_export_worker_once(), 1)

            out_image = Path(pipeline.config["storage"]["root"]) / "jobs" / job_id / "exports" / "photo_export.png"
            sidecar = Path(pipeline.config["storage"]["root"]) / "jobs" / job_id / "exports" / "photo_export.sidecar.json"
            self.assertTrue(out_image.exists())
            self.assertTrue(sidecar.exists())

            final = pipeline.queue.fetch_job(job_id)
            self.assertEqual(final["status"], "completed")
            self.assertTrue(final["export_done"])

    def test_validation_failure_blocks_downstream(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg_path = self._make_config(root, cv_min_bytes=10_000_000)

            front = root / "front.png"
            back = root / "back.png"
            make_png(front, 1600, 1600)
            make_png(back, 1600, 1600)
            pipeline = Pipeline(cfg_path)
            created = pipeline.create_job(str(front), str(back), [])
            job_id = created["job_id"]

            self.assertEqual(pipeline.run_cv_worker_once(), 1)
            self.assertEqual(pipeline.queue.fetch_job(job_id)["status"], "validation_failed")
            self.assertEqual(pipeline.run_ocr_worker_once(), 0)
            self.assertEqual(pipeline.run_metadata_worker_once(), 0)

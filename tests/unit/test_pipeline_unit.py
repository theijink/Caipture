from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from caipture.pipeline import Pipeline
from tests.test_utils import cv2, make_jpeg, make_photo_scene, make_png


class PipelineUnitTests(unittest.TestCase):
    def _make_config(self, root: Path) -> Path:
        cfg = {
            "storage": {"root": str(root / "storage")},
            "upload": {"allowed_image_formats": ["png", "jpg", "jpeg"], "min_longest_side_px": 1500},
            "cv": {"engine": "cv", "min_short_side_px": 900, "min_bytes": 100},
            "ocr": {"engine": "ocr", "language": "eng"},
            "metadata": {
                "pipeline_version": "0.2.0",
                "config_version": "test",
                "enable_llm_gateway": False,
                "location_dictionary": {"enschede": {"name": "Enschede", "country_code": "NL", "lat": 1.0, "lon": 1.0}},
            },
            "review": {"auto_approve_min_confidence": 0.75},
            "export": {"profile": "default"},
            "queue": {"db_path": str(root / "storage" / "runtime" / "jobs.sqlite3"), "max_retries": 2},
        }
        path = root / "config.json"
        path.write_text(json.dumps(cfg), encoding="utf-8")
        return path

    def test_upload_rejects_small_image(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg_path = self._make_config(root)
            subject = root / "front.png"
            back = root / "back.png"
            make_png(subject, 200, 200)
            make_png(back, 200, 200)
            pipeline = Pipeline(cfg_path)
            with self.assertRaises(ValueError):
                pipeline.create_job(subject_path=str(subject), back_path=str(back), context_paths=[])

    def test_upload_stores_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg_path = self._make_config(root)
            subject = root / "front.png"
            back = root / "back.png"
            make_png(subject, 1700, 1500)
            make_png(back, 1700, 1500)
            pipeline = Pipeline(cfg_path)
            result = pipeline.create_job(subject_path=str(subject), back_path=str(back), context_paths=[])
            job_dir = Path(pipeline.config["storage"]["root"]) / "jobs" / result["job_id"]
            self.assertTrue((job_dir / "inputs" / "front.png").exists())
            self.assertTrue((job_dir / "inputs" / "back.png").exists())

    def test_upload_accepts_jpeg_subject_and_preserves_original_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg_path = self._make_config(root)
            subject = root / "phone.jpg"
            make_jpeg(subject, 3024, 4032)
            pipeline = Pipeline(cfg_path)
            result = pipeline.create_job(subject_path=str(subject), context_paths=[])
            job_dir = Path(pipeline.config["storage"]["root"]) / "jobs" / result["job_id"]
            self.assertTrue((job_dir / "inputs" / "front.jpg").exists())

    def test_manual_context_aliases_are_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg_path = self._make_config(root)
            subject = root / "phone.jpg"
            make_jpeg(subject, 3024, 4032)
            pipeline = Pipeline(cfg_path)
            result = pipeline.create_job(
                subject_path=str(subject),
                manual_context={
                    "manual_date": "1954-07-12",
                    "manual_location": "Enschede",
                    "description": "Family portrait at the market",
                },
            )
            job = pipeline.queue.fetch_job(result["job_id"])
            self.assertEqual(
                job["manual_context"],
                {
                    "date": "1954-07-12",
                    "location": "Enschede",
                    "comment": "Family portrait at the market",
                },
            )

    @unittest.skipIf(cv2 is None, "opencv-python not available")
    def test_cv_transform_finds_subject_photo_in_generic_scene(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg_path = self._make_config(root)
            scene = root / "scene.jpg"
            make_photo_scene(scene)
            pipeline = Pipeline(cfg_path)
            cropped = root / "cropped.png"
            rectified = root / "rectified.png"

            pipeline._run_cv_transform(scene, cropped, rectified)

            self.assertTrue(cropped.exists())
            cropped_image = cv2.imread(str(cropped))
            source_image = cv2.imread(str(scene))
            self.assertIsNotNone(cropped_image)
            self.assertIsNotNone(source_image)
            cropped_area = cropped_image.shape[0] * cropped_image.shape[1]
            source_area = source_image.shape[0] * source_image.shape[1]
            self.assertLess(cropped_area, source_area * 0.8)

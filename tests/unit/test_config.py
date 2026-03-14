from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from caipture.config import ConfigError, load_config


class ConfigTests(unittest.TestCase):
    def test_load_config_success(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "storage": {"root": "storage"},
                        "upload": {"allowed_image_formats": ["png", "jpg", "jpeg"], "min_longest_side_px": 1500},
                        "cv": {},
                        "ocr": {},
                        "metadata": {},
                        "review": {"auto_approve_min_confidence": 0.8},
                        "export": {},
                        "queue": {"max_retries": 1, "db_path": "storage/runtime/jobs.sqlite3"},
                    }
                ),
                encoding="utf-8",
            )
            cfg = load_config(path)
            self.assertEqual(cfg["upload"]["min_longest_side_px"], 1500)

    def test_load_config_missing_section(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.json"
            path.write_text(json.dumps({"storage": {"root": "storage"}}), encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)

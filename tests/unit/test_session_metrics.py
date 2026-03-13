from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from caipture.session_metrics import SessionMetrics


class SessionMetricsTests(unittest.TestCase):
    def test_increments_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            metrics = SessionMetrics(Path(td) / "session_metrics.json")
            metrics.increment("llm_requests_total")
            metrics.increment_stage("metadata")
            snap = metrics.snapshot()
            self.assertEqual(snap["llm_requests_total"], 1)
            self.assertEqual(snap["stages"]["metadata"], 1)

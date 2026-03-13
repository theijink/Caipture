from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from caipture.queue import JobQueue


class QueueJournalTests(unittest.TestCase):
    def test_queue_event_writes_journal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "runtime" / "jobs.sqlite3"
            queue = JobQueue(db_path)
            queue.create_job(
                {
                    "job_id": "job_1",
                    "item_id": "item_1",
                    "front_input": "inputs/front.png",
                    "back_input": "inputs/back.png",
                    "context_inputs": [],
                }
            )
            queue.add_event("job_1", "test", "something_happened", {"ok": True})
            journal = db_path.parent / "journal.jsonl"
            text = journal.read_text(encoding="utf-8")
            self.assertIn("something_happened", text)
            self.assertIn("create_job", text)

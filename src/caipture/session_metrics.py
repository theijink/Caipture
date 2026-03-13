from __future__ import annotations

from pathlib import Path
from threading import Lock

from caipture.utils import read_json, utc_now_iso, write_json


class SessionMetrics:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            write_json(
                self.path,
                {
                    "started_at": utc_now_iso(),
                    "llm_requests_total": 0,
                    "llm_enabled_requests": 0,
                    "stages": {
                        "cv": 0,
                        "ocr": 0,
                        "metadata": 0,
                        "export": 0,
                    },
                },
            )

    def snapshot(self) -> dict:
        with self._lock:
            return read_json(self.path)

    def increment(self, field: str, delta: int = 1) -> None:
        with self._lock:
            data = read_json(self.path)
            data[field] = int(data.get(field, 0)) + delta
            write_json(self.path, data)

    def increment_stage(self, stage: str, delta: int = 1) -> None:
        with self._lock:
            data = read_json(self.path)
            stages = dict(data.get("stages", {}))
            stages[stage] = int(stages.get(stage, 0)) + delta
            data["stages"] = stages
            write_json(self.path, data)

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

from caipture.utils import utc_now_iso


class Journal:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def log(self, source: str, action: str, details: dict[str, Any] | None = None) -> None:
        entry = {
            "timestamp": utc_now_iso(),
            "source": source,
            "action": action,
            "details": details or {},
        }
        line = json.dumps(entry, sort_keys=True)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def tail(self, count: int = 40) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()
        out: list[dict[str, Any]] = []
        for raw in lines[-count:]:
            raw = raw.strip()
            if not raw:
                continue
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        return out

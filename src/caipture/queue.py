from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from caipture.journal import Journal
from caipture.models import JobStatus
from caipture.utils import utc_now_iso


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    front_input TEXT NOT NULL,
    back_input TEXT NOT NULL,
    context_inputs TEXT NOT NULL,
    error_code TEXT,
    error_message TEXT,
    cv_done INTEGER NOT NULL DEFAULT 0,
    ocr_done INTEGER NOT NULL DEFAULT 0,
    metadata_done INTEGER NOT NULL DEFAULT 0,
    review_done INTEGER NOT NULL DEFAULT 0,
    export_done INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    event TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    details TEXT NOT NULL
);
"""


class JobQueue:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.journal = Journal(self.db_path.parent / "journal.jsonl")
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def create_job(self, job: dict[str, Any]) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id,item_id,status,created_at,updated_at,front_input,back_input,context_inputs
                ) VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    job["job_id"],
                    job["item_id"],
                    JobStatus.UPLOADED.value,
                    now,
                    now,
                    job["front_input"],
                    job["back_input"],
                    json.dumps(job.get("context_inputs", [])),
                ),
            )
        self.add_event(job["job_id"], "upload", "created", {"status": JobStatus.UPLOADED.value})
        self.journal.log("queue", "create_job", {"job_id": job["job_id"], "item_id": job["item_id"]})

    def set_status(self, job_id: str, status: JobStatus, error_code: str | None = None, error_message: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status=?, updated_at=?, error_code=?, error_message=? WHERE job_id=?",
                (status.value, utc_now_iso(), error_code, error_message, job_id),
            )
        self.journal.log(
            "queue",
            "set_status",
            {"job_id": job_id, "status": status.value, "error_code": error_code, "error_message": error_message},
        )

    def update_flags(self, job_id: str, **flags: bool) -> None:
        parts = []
        values: list[Any] = []
        for key, value in flags.items():
            parts.append(f"{key}=?")
            values.append(1 if value else 0)
        parts.append("updated_at=?")
        values.append(utc_now_iso())
        values.append(job_id)
        with self._connect() as conn:
            conn.execute(f"UPDATE jobs SET {', '.join(parts)} WHERE job_id=?", values)

    def fetch_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                return None
            data = dict(row)
            data["context_inputs"] = json.loads(data["context_inputs"])
            for key in ["cv_done", "ocr_done", "metadata_done", "review_done", "export_done"]:
                data[key] = bool(data[key])
            return data

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM jobs ORDER BY created_at").fetchall()
        out = []
        for row in rows:
            data = dict(row)
            data["context_inputs"] = json.loads(data["context_inputs"])
            for key in ["cv_done", "ocr_done", "metadata_done", "review_done", "export_done"]:
                data[key] = bool(data[key])
            out.append(data)
        return out

    def add_event(self, job_id: str, stage: str, event: str, details: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO events(job_id, stage, event, timestamp, details) VALUES (?,?,?,?,?)",
                (job_id, stage, event, utc_now_iso(), json.dumps(details, sort_keys=True)),
            )
        self.journal.log("queue", "event", {"job_id": job_id, "stage": stage, "event": event, "details": details})

    def fetch_events(self, job_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT stage, event, timestamp, details FROM events WHERE job_id=? ORDER BY id",
                (job_id,),
            ).fetchall()
        return [
            {
                "stage": row["stage"],
                "event": row["event"],
                "timestamp": row["timestamp"],
                "details": json.loads(row["details"]),
            }
            for row in rows
        ]

    def select_for_cv(self) -> list[dict[str, Any]]:
        return [j for j in self.list_jobs() if j["status"] in {JobStatus.QUEUED.value, JobStatus.UPLOADED.value} and not j["cv_done"]]

    def select_for_ocr(self) -> list[dict[str, Any]]:
        return [j for j in self.list_jobs() if j["cv_done"] and not j["ocr_done"] and j["status"] not in {JobStatus.VALIDATION_FAILED.value, JobStatus.FAILED.value}]

    def select_for_metadata(self) -> list[dict[str, Any]]:
        return [j for j in self.list_jobs() if j["cv_done"] and j["ocr_done"] and not j["metadata_done"] and j["status"] != JobStatus.FAILED.value]

    def select_for_export(self) -> list[dict[str, Any]]:
        return [j for j in self.list_jobs() if j["metadata_done"] and j["review_done"] and not j["export_done"] and j["status"] != JobStatus.FAILED.value]

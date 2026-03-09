from __future__ import annotations

import shutil
from pathlib import Path

from caipture.models import FileRef
from caipture.utils import sha256_file


class Storage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.jobs_root = root / "jobs"

    def init_layout(self) -> None:
        for rel in ["jobs", "uploads", "exports", "logs"]:
            (self.root / rel).mkdir(parents=True, exist_ok=True)

    def job_dir(self, job_id: str) -> Path:
        return self.jobs_root / job_id

    def create_job_dirs(self, job_id: str) -> None:
        base = self.job_dir(job_id)
        for rel in ["inputs", "derived", "metadata", "logs", "exports"]:
            (base / rel).mkdir(parents=True, exist_ok=True)

    def ingest_file(self, src: Path, job_id: str, target_name: str) -> FileRef:
        dest = self.job_dir(job_id) / "inputs" / target_name
        shutil.copy2(src, dest)
        src_sidecar = src.with_suffix(".txt")
        if src_sidecar.exists():
            shutil.copy2(src_sidecar, dest.with_suffix(".txt"))
        return FileRef(
            path=str(Path("inputs") / target_name),
            sha256=sha256_file(dest),
            bytes=dest.stat().st_size,
        )

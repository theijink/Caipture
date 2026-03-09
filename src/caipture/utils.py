from __future__ import annotations

import hashlib
import json
import struct
from datetime import UTC, datetime
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def detect_png_size(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as handle:
        sig = handle.read(8)
        if sig != b"\x89PNG\r\n\x1a\n":
            return None
        chunk_len = handle.read(4)
        chunk_type = handle.read(4)
        if len(chunk_len) != 4 or chunk_type != b"IHDR":
            return None
        width, height = struct.unpack(">II", handle.read(8))
        return int(width), int(height)


def image_dimensions(path: Path) -> tuple[int, int] | None:
    # PoC parser intentionally supports PNG for deterministic test fixtures.
    return detect_png_size(path)

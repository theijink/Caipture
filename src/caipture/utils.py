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


def detect_jpeg_size(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as handle:
        data = handle.read(2)
        if data != b"\xff\xd8":
            return None

        while True:
            marker_start = handle.read(1)
            if not marker_start:
                return None
            if marker_start != b"\xff":
                continue
            marker = handle.read(1)
            if not marker:
                return None
            if marker in {b"\xd8", b"\xd9"}:
                continue
            length_raw = handle.read(2)
            if len(length_raw) != 2:
                return None
            length = struct.unpack(">H", length_raw)[0]
            if length < 2:
                return None
            if marker in {b"\xc0", b"\xc1", b"\xc2", b"\xc3", b"\xc5", b"\xc6", b"\xc7", b"\xc9", b"\xca", b"\xcb", b"\xcd", b"\xce", b"\xcf"}:
                precision = handle.read(1)
                if not precision:
                    return None
                size_raw = handle.read(4)
                if len(size_raw) != 4:
                    return None
                height, width = struct.unpack(">HH", size_raw)
                return int(width), int(height)
            handle.seek(length - 2, 1)


def image_dimensions(path: Path) -> tuple[int, int] | None:
    # PoC parser supports PNG and JPEG by file signature.
    png = detect_png_size(path)
    if png:
        return png
    return detect_jpeg_size(path)

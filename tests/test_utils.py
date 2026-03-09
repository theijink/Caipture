from __future__ import annotations

import binascii
import struct
import zlib
from pathlib import Path


def make_png(path: Path, width: int, height: int, rgb: tuple[int, int, int] = (120, 120, 120)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + chunk_type
            + data
            + struct.pack(">I", binascii.crc32(chunk_type + data) & 0xFFFFFFFF)
        )

    png_sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)

    row = bytes([0, *rgb * width])
    raw = row * height
    idat = zlib.compress(raw)

    payload = png_sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")
    path.write_bytes(payload)

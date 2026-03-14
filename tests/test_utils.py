from __future__ import annotations

import binascii
import struct
import zlib
from pathlib import Path

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - optional test dependency
    cv2 = None
    np = None


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


def make_jpeg(path: Path, width: int, height: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def segment(marker: bytes, payload: bytes) -> bytes:
        return marker + struct.pack(">H", len(payload) + 2) + payload

    app0 = b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sof0 = (
        b"\x08"
        + struct.pack(">H", height)
        + struct.pack(">H", width)
        + b"\x03"
        + b"\x01\x11\x00"
        + b"\x02\x11\x00"
        + b"\x03\x11\x00"
    )
    payload = b"".join(
        [
            b"\xff\xd8",
            segment(b"\xff\xe0", app0),
            segment(b"\xff\xc0", sof0),
            b"\xff\xd9",
        ]
    )
    path.write_bytes(payload)


def make_photo_scene(path: Path, width: int = 2200, height: int = 1600, angle_deg: float = 11.0) -> None:
    if cv2 is None or np is None:  # pragma: no cover - optional dependency guard
        raise RuntimeError("opencv-python and numpy are required for make_photo_scene")

    path.parent.mkdir(parents=True, exist_ok=True)
    canvas = np.full((height, width, 3), (72, 92, 112), dtype=np.uint8)
    noise = np.random.default_rng(1234).integers(-10, 11, size=canvas.shape, dtype=np.int16)
    canvas = np.clip(canvas.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    rect_w, rect_h = int(width * 0.63), int(height * 0.68)
    center = (width // 2, height // 2)
    rect = ((center[0], center[1]), (rect_w, rect_h), angle_deg)
    box = cv2.boxPoints(rect).astype(np.int32)

    shadow = box + np.array([28, 36], dtype=np.int32)
    cv2.fillConvexPoly(canvas, shadow, (28, 36, 44))
    cv2.fillConvexPoly(canvas, box, (235, 233, 226))
    inner_rect = ((center[0], center[1]), (rect_w - 90, rect_h - 90), angle_deg)
    inner_box = cv2.boxPoints(inner_rect).astype(np.int32)
    cv2.fillConvexPoly(canvas, inner_box, (186, 176, 150))
    cv2.polylines(canvas, [box], isClosed=True, color=(248, 246, 240), thickness=24)
    cv2.polylines(canvas, [inner_box], isClosed=True, color=(84, 74, 60), thickness=10)

    ext = path.suffix.lower()
    params = [cv2.IMWRITE_JPEG_QUALITY, 95] if ext in {".jpg", ".jpeg"} else []
    cv2.imwrite(str(path), canvas, params)

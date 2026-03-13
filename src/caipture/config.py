from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path("deploy/configs/dev/config.json")


class ConfigError(RuntimeError):
    pass


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(config_path or os.getenv("CAIPTURE_CONFIG", DEFAULT_CONFIG_PATH))
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    _validate_config(data)
    return data


def _validate_config(config: dict[str, Any]) -> None:
    required_root = [
        "storage",
        "upload",
        "cv",
        "ocr",
        "metadata",
        "review",
        "export",
        "queue",
    ]
    missing = [key for key in required_root if key not in config]
    if missing:
        raise ConfigError(f"Missing config sections: {', '.join(missing)}")

    min_px = config["upload"].get("min_longest_side_px")
    if not isinstance(min_px, int) or min_px < 1:
        raise ConfigError("upload.min_longest_side_px must be a positive integer")

    allowed = config["upload"].get("allowed_image_formats")
    if not isinstance(allowed, list) or not all(isinstance(x, str) for x in allowed):
        raise ConfigError("upload.allowed_image_formats must be a list of strings")

    review_threshold = config["review"].get("auto_approve_min_confidence")
    if not isinstance(review_threshold, (float, int)):
        raise ConfigError("review.auto_approve_min_confidence must be numeric")
    if not 0.0 <= float(review_threshold) <= 1.0:
        raise ConfigError("review.auto_approve_min_confidence must be in [0.0, 1.0]")

    retries = config["queue"].get("max_retries")
    if not isinstance(retries, int) or retries < 0:
        raise ConfigError("queue.max_retries must be a non-negative integer")

    monitoring = config.get("monitoring", {})
    if monitoring:
        refresh_seconds = monitoring.get("refresh_seconds", 5)
        if not isinstance(refresh_seconds, int) or refresh_seconds < 1:
            raise ConfigError("monitoring.refresh_seconds must be a positive integer")

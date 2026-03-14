from __future__ import annotations

import os
import time

from caipture.pipeline import Pipeline, cv2, np


def main() -> None:
    if cv2 is None or np is None:
        print("worker-cv warning: OpenCV is not available; falling back to ImageMagick-only trim, which is less reliable for generic photo-of-a-photo inputs.")
    pipeline = Pipeline(os.getenv("CAIPTURE_CONFIG"))
    interval = float(os.getenv("CAIPTURE_WORKER_INTERVAL", "1"))
    while True:
        pipeline.run_cv_worker_once()
        time.sleep(interval)


if __name__ == "__main__":
    main()

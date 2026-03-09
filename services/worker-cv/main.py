from __future__ import annotations

import os
import time

from caipture.pipeline import Pipeline


def main() -> None:
    pipeline = Pipeline(os.getenv("CAIPTURE_CONFIG"))
    interval = float(os.getenv("CAIPTURE_WORKER_INTERVAL", "1"))
    while True:
        pipeline.run_cv_worker_once()
        time.sleep(interval)


if __name__ == "__main__":
    main()

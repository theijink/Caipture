from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from caipture.pipeline import Pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="caipture")
    parser.add_argument("--config", default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)

    upload = sub.add_parser("upload")
    upload.add_argument("--front", required=True)
    upload.add_argument("--back", required=True)
    upload.add_argument("--context", action="append", default=[])

    sub.add_parser("run-cv-once")
    sub.add_parser("run-ocr-once")
    sub.add_parser("run-metadata-once")
    sub.add_parser("run-export-once")
    sub.add_parser("run-all-once")

    worker = sub.add_parser("run-worker")
    worker.add_argument("--stage", choices=["cv", "ocr", "metadata", "export"], required=True)
    worker.add_argument("--interval", type=float, default=1.0)

    review = sub.add_parser("review-approve")
    review.add_argument("--job-id", required=True)
    review.add_argument("--approved-by", required=True)
    review.add_argument("--notes", default="")

    status = sub.add_parser("status")
    status.add_argument("--job-id", required=False)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    pipeline = Pipeline(args.config)

    if args.cmd == "upload":
        result = pipeline.create_job(args.front, args.back, args.context)
        print(json.dumps(result))
        return 0

    if args.cmd == "run-cv-once":
        print(json.dumps({"processed": pipeline.run_cv_worker_once()}))
        return 0
    if args.cmd == "run-ocr-once":
        print(json.dumps({"processed": pipeline.run_ocr_worker_once()}))
        return 0
    if args.cmd == "run-metadata-once":
        print(json.dumps({"processed": pipeline.run_metadata_worker_once()}))
        return 0
    if args.cmd == "run-export-once":
        print(json.dumps({"processed": pipeline.run_export_worker_once()}))
        return 0
    if args.cmd == "run-all-once":
        print(json.dumps(pipeline.run_all_once()))
        return 0

    if args.cmd == "run-worker":
        while True:
            if args.stage == "cv":
                pipeline.run_cv_worker_once()
            elif args.stage == "ocr":
                pipeline.run_ocr_worker_once()
            elif args.stage == "metadata":
                pipeline.run_metadata_worker_once()
            else:
                pipeline.run_export_worker_once()
            time.sleep(args.interval)

    if args.cmd == "review-approve":
        pipeline.apply_review(args.job_id, args.approved_by, args.notes)
        print(json.dumps({"ok": True}))
        return 0

    if args.cmd == "status":
        if args.job_id:
            print(json.dumps(pipeline.queue.fetch_job(args.job_id), indent=2, sort_keys=True))
        else:
            print(json.dumps(pipeline.queue.list_jobs(), indent=2, sort_keys=True))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

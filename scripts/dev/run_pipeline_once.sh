#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

export PYTHONPATH=src
CONFIG="${CAIPTURE_CONFIG:-deploy/configs/dev/config.json}"

python3 -m caipture.cli --config "$CONFIG" run-cv-once
python3 -m caipture.cli --config "$CONFIG" run-ocr-once
python3 -m caipture.cli --config "$CONFIG" run-metadata-once
python3 -m caipture.cli --config "$CONFIG" run-export-once

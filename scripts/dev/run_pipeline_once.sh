#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

export PYTHONPATH=src
CONFIG="${CAIPTURE_CONFIG:-deploy/configs/dev/config.json}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
if [[ -x "venv/bin/python" ]]; then
  PYTHON_BIN="venv/bin/python"
fi

"$PYTHON_BIN" -m caipture.cli --config "$CONFIG" run-cv-once
"$PYTHON_BIN" -m caipture.cli --config "$CONFIG" run-ocr-once
"$PYTHON_BIN" -m caipture.cli --config "$CONFIG" run-metadata-once
"$PYTHON_BIN" -m caipture.cli --config "$CONFIG" run-export-once

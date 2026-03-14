#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

mkdir -p storage/runtime
rm -f storage/runtime/session_metrics.json

export PYTHONPATH=src
export CAIPTURE_CONFIG="${CAIPTURE_CONFIG:-deploy/configs/dev/config.json}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
if [[ -x "venv/bin/python" ]]; then
  PYTHON_BIN="venv/bin/python"
fi

"$PYTHON_BIN" services/web/server.py > storage/runtime/web.log 2>&1 &
echo $! > storage/runtime/web.pid
"$PYTHON_BIN" -m caipture.cli --config "$CAIPTURE_CONFIG" run-worker --stage cv --interval 1 > storage/runtime/worker-cv.log 2>&1 &
echo $! > storage/runtime/worker-cv.pid
"$PYTHON_BIN" -m caipture.cli --config "$CAIPTURE_CONFIG" run-worker --stage ocr --interval 1 > storage/runtime/worker-ocr.log 2>&1 &
echo $! > storage/runtime/worker-ocr.pid
"$PYTHON_BIN" -m caipture.cli --config "$CAIPTURE_CONFIG" run-worker --stage metadata --interval 1 > storage/runtime/worker-metadata.log 2>&1 &
echo $! > storage/runtime/worker-metadata.pid
"$PYTHON_BIN" -m caipture.cli --config "$CAIPTURE_CONFIG" run-worker --stage export --interval 1 > storage/runtime/worker-export.log 2>&1 &
echo $! > storage/runtime/worker-export.pid
"$PYTHON_BIN" services/llm-gateway/main.py > storage/runtime/llm-gateway.log 2>&1 &
echo $! > storage/runtime/llm-gateway.pid

echo "Caipture services started. PID files in storage/runtime/*.pid"

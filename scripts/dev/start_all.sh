#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

mkdir -p storage/runtime

export PYTHONPATH=src
export CAIPTURE_CONFIG="${CAIPTURE_CONFIG:-deploy/configs/dev/config.json}"

python3 services/web/server.py > storage/runtime/web.log 2>&1 &
echo $! > storage/runtime/web.pid
python3 -m caipture.cli --config "$CAIPTURE_CONFIG" run-worker --stage cv --interval 1 > storage/runtime/worker-cv.log 2>&1 &
echo $! > storage/runtime/worker-cv.pid
python3 -m caipture.cli --config "$CAIPTURE_CONFIG" run-worker --stage ocr --interval 1 > storage/runtime/worker-ocr.log 2>&1 &
echo $! > storage/runtime/worker-ocr.pid
python3 -m caipture.cli --config "$CAIPTURE_CONFIG" run-worker --stage metadata --interval 1 > storage/runtime/worker-metadata.log 2>&1 &
echo $! > storage/runtime/worker-metadata.pid
python3 -m caipture.cli --config "$CAIPTURE_CONFIG" run-worker --stage export --interval 1 > storage/runtime/worker-export.log 2>&1 &
echo $! > storage/runtime/worker-export.pid
python3 services/llm-gateway/main.py > storage/runtime/llm-gateway.log 2>&1 &
echo $! > storage/runtime/llm-gateway.pid

echo "Caipture services started. PID files in storage/runtime/*.pid"

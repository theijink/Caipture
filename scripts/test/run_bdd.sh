#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

export PYTHONPATH=src
PYTHON_BIN="${PYTHON_BIN:-python3}"
if [[ -x "venv/bin/python" ]]; then
  PYTHON_BIN="venv/bin/python"
fi
"$PYTHON_BIN" -c "import behave" >/dev/null 2>&1 || {
  echo "behave is not installed. Install dev dependencies: python3 -m pip install -r requirements-dev.txt"
  exit 1
}
"$PYTHON_BIN" -m behave tests/bdd/features

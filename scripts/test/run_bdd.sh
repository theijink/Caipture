#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

export PYTHONPATH=src
python3 -c "import behave" >/dev/null 2>&1 || {
  echo "behave is not installed. Install dev dependencies: python3 -m pip install -r requirements-dev.txt"
  exit 1
}
python3 -m behave tests/bdd/features

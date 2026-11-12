#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
mkdir -p .test-tmp .tmp
export TMPDIR="$ROOT/.test-tmp"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$ROOT/src"
export UV_CACHE_DIR="$ROOT/.tmp/uv-cache"
export UV_PYTHON_DOWNLOADS=never
uv lock --check --offline --no-managed-python --python python3
python3 -m unittest discover -s tests -v
python3 scripts/build.py
unset PYTHONPATH
python3 -I dist/brain.pyz --version
./dist/brain.pyz --version
python3 -I dist/brain.pyz --help > .tmp/help.txt

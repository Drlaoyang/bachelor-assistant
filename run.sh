#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
fi

if ! .venv/bin/python -c "import flet" >/dev/null 2>&1; then
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/pip install \
        "flet==1.0.4" \
        "platformdirs>=4" \
        "pymupdf==1.27.2.3" \
        "rapidocr==3.10.0" \
        "onnxruntime==1.27.0"
fi

exec .venv/bin/flet run src/main.py

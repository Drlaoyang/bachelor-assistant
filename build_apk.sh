#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

VERSION="0.1.0"
APK_NAME="sdu-ce-ledger-${VERSION}-arm64.apk"

if [ ! -x .venv/bin/flet ]; then
    echo "未找到 .venv/bin/flet，请先运行 ./run.sh 初始化环境。" >&2
    exit 1
fi

mkdir -p dist
.venv/bin/flet build apk --python-version 3.13 --arch arm64-v8a --yes
cp build/apk/sdu-ce-ledger.apk "dist/${APK_NAME}"
(
    cd dist
    sha256sum "${APK_NAME}" > SHA256SUMS
)

echo "APK: dist/${APK_NAME}"
echo "SHA256: dist/SHA256SUMS"

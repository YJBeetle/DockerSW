#!/usr/bin/env bash
set -Eeuo pipefail

SWCLI_SOURCE="${1:-/opt/swcli}"
WIN_PYTHON="${SWCLI_WINDOWS_PYTHON:-C:\\Python311\\python.exe}"

test -f "${SWCLI_SOURCE}/pyproject.toml" || {
    echo "SWCLI source is unavailable: ${SWCLI_SOURCE}" >&2
    exit 1
}

windows_source="$(winepath -w "${SWCLI_SOURCE}")"
wine "${WIN_PYTHON}" -m pip install \
    --no-cache-dir --no-deps --no-build-isolation "${windows_source}"
wine "${WIN_PYTHON}" -m swcli version --json
wineserver -w

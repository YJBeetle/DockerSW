#!/usr/bin/env bash
set -Eeuo pipefail

# Installation/repair is host-owned; SWCLI owns shared read-only assertions.
outdir="${1:-$(mktemp -d "${SW_SMOKE_EVIDENCE_DIR:-/tmp}/swcli-toolbox.XXXXXX")}"
prefix="${2:-${WINEPREFIX:?usage: verify-toolbox.sh [OUTPUT_DIRECTORY] [WINE_PREFIX]}}"
mkdir -p "${outdir}"
chmod 755 "${outdir}"
PYTHONPATH="${SWCLI_SOURCE:-/opt/swcli/src}:${SWCLI_DEPS:-/opt/swcli-deps}/linux" \
    python3 /opt/swcli/scripts/ci/verify-toolbox.py \
    --output-dir "${outdir}" --wine-prefix "${prefix}" --require-toolbox \
    --cli-command /usr/local/bin/sw-cli

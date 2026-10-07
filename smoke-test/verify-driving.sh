#!/usr/bin/env bash
set -Eeuo pipefail

# Reuse SWCLI's protocol gate through the Linux CLI entry point. Extra native
# models/evidence stay outside the six published export artifacts.
dimension_outdir="$(mktemp -d "${SW_SMOKE_EVIDENCE_DIR:-/tmp}/swcli-driving.XXXXXX")"
# mktemp defaults to 0700; the host runner must be able to collect CI evidence.
chmod 755 "${dimension_outdir}"
PYTHONPATH="${SWCLI_SOURCE:-/opt/swcli/src}:${SWCLI_DEPS:-/opt/swcli-deps}/linux" \
    python3 /opt/swcli/scripts/ci/verify-driving-dimensions.py \
    --output-dir "${dimension_outdir}" \
    --host-output-dir "$(winepath -w "${dimension_outdir}")" \
    --cli-command /usr/local/bin/sw-cli

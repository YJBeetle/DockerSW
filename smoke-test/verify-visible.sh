#!/usr/bin/env bash
set -Eeuo pipefail

# DockerSW owns Wine paths and container lifecycle; SWCLI owns the assertions.
workspace="${WINEPREFIX:-/root/.wine}/drive_c"
outdir="${SW_SMOKE_EVIDENCE_DIR:-/ci-smoke}/visible"
mkdir -p "${outdir}"
chmod 755 "${outdir}"
PYTHONPATH="${SWCLI_SOURCE:-/opt/swcli/src}:${SWCLI_DEPS:-/opt/swcli-deps}/linux" \
    python3 /opt/swcli/scripts/ci/verify-visible.py \
    --output-dir "${outdir}" --cli-command /usr/local/bin/sw-cli \
    --sample-part "$(winepath -w "${workspace}/users/Public/Documents/SOLIDWORKS/SOLIDWORKS 2025/samples/learn/Paper Airplane.SLDPRT")"
# daemon stop is asynchronous: prove the exact endpoint stopped before success.
deadline=$((SECONDS + 15))
while [ "${SECONDS}" -lt "${deadline}" ]; do
    if status="$(sw-cli --request-timeout 2 daemon status --json 2>/dev/null)"; then
        sleep 1
    elif jq -e '.success == false and .error.code == "ConnectionRefusedError"' <<<"${status}" >/dev/null; then
        exit 0
    elif jq -e '.success == false and (.error.code == "TimeoutError" or .error.code == "ConnectionResetError")' <<<"${status}" >/dev/null; then
        sleep 1  # A shutdown transition is not yet proof of a stopped endpoint.
    else
        echo "Visible daemon shutdown could not be verified: ${status}" >&2
        exit 1
    fi
done
echo 'Visible daemon did not stop within 15 seconds' >&2
exit 1

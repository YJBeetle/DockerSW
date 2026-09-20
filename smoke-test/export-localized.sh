#!/usr/bin/env bash
set -Eeuo pipefail

workspace="${SW_SMOKE_WORKSPACE:-/root/.wine/drive_c}"
outdir="${SW_SMOKE_OUTDIR:-/ci-smoke/output}"
language_directory="${SW_LANGUAGE_RESOURCE_DIR:?SW_LANGUAGE_RESOURCE_DIR is required}"
expected_language="${SW_SOLIDWORKS_LANGUAGE:?SW_SOLIDWORKS_LANGUAGE is required}"

test -d "${workspace}/Program Files/SOLIDWORKS/lang/${language_directory}"

status_json="$(sw-cli daemon status --json)"
actual_language="$(
    python3 -c 'import json, sys; print(json.load(sys.stdin)["result"]["host"]["language"])' \
        <<<"${status_json}"
)"
if [ "${actual_language}" != "${expected_language}" ]; then
    printf 'Expected SOLIDWORKS language %s, got %s\n' \
        "${expected_language}" "${actual_language}" >&2
    exit 1
fi

sw-cli document open \
    "${workspace}/users/Public/Documents/SOLIDWORKS/SOLIDWORKS 2025/samples/learn/Paper Airplane.SLDPRT" --json
sw-cli document export "${outdir}/Paper Airplane.STEP" --json
sw-cli document close --discard --json
sw-cli daemon stop --json

test -s "${outdir}/Paper Airplane.STEP"

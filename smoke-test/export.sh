#!/usr/bin/env bash
set -Eeuo pipefail

workspace="${SW_SMOKE_WORKSPACE:-/root/.wine/drive_c}"
outdir="${SW_SMOKE_OUTDIR:-/ci-smoke/output}"

# This workflow is deliberately explicit so downstream CI users can copy it
# and replace only the source/output paths.

# Drawing: export one PDF and one DWG, then discard any exporter modifications.
sw-cli document open \
    "${workspace}/Program Files/SOLIDWORKS/sldBenchmarking/Macro/Mold/bezel moldbase.slddrw" --json
sw-cli document export "${outdir}/bezel moldbase.PDF" --json
sw-cli document export "${outdir}/bezel moldbase.DWG" --json
sw-cli document close --discard --json

# Assembly: export one neutral STEP artifact.
sw-cli document open \
    "${workspace}/Program Files/SOLIDWORKS/sldBenchmarking/Macro/Mold/bezel moldbase.sldasm" --json
sw-cli document export "${outdir}/bezel moldbase.STEP" --json
sw-cli document close --discard --json

# Drawing: the DWG exporter may mark the source as modified without saving it.
sw-cli document open \
    "${workspace}/users/Public/Documents/SOLIDWORKS/SOLIDWORKS 2025/samples/introsw/cabinet_bath.slddrw" --json
sw-cli document export "${outdir}/cabinet_bath.PDF" --json
sw-cli document export "${outdir}/cabinet_bath.DWG" --json
sw-cli document close --discard --json

# Part: export one neutral STEP artifact.
sw-cli document open \
    "${workspace}/users/Public/Documents/SOLIDWORKS/SOLIDWORKS 2025/samples/learn/Paper Airplane.SLDPRT" --json
sw-cli document export "${outdir}/Paper Airplane.STEP" --json
sw-cli document close --discard --json

bash "$(dirname "${BASH_SOURCE[0]}")/verify-swcli.sh" "${workspace}"

sw-cli daemon stop --json

#!/usr/bin/env bash
set -Eeuo pipefail

workspace="${SW_SMOKE_WORKSPACE:-/root/.wine/drive_c}"
outdir="${SW_SMOKE_OUTDIR:-/ci-smoke/output}"

# This workflow is deliberately explicit so downstream CI users can copy it
# and replace only the source/output paths.
mkdir -p "${outdir}"
# This is a delivery smoke, not source validation: ordinary exports may report
# warnings. Do not rebuild/save samples; close discards exporter modifications.

# Drawing: export one PDF and one DWG, then discard any exporter modifications.
sw-cli document open \
    "${workspace}/Program Files/SOLIDWORKS/sldBenchmarking/Macro/Mold/bezel moldbase.slddrw" --json
sw-cli document export --json "${outdir}/bezel moldbase.PDF"
sw-cli document export --json "${outdir}/bezel moldbase.DWG"
sw-cli document close --discard --json

# Assembly: export one neutral STEP artifact.
sw-cli document open \
    "${workspace}/Program Files/SOLIDWORKS/sldBenchmarking/Macro/Mold/bezel moldbase.sldasm" --json
sw-cli document export --json "${outdir}/bezel moldbase.STEP"
sw-cli document close --discard --json

# Drawing: the DWG exporter may mark the source as modified without saving it.
sw-cli document open \
    "${workspace}/users/Public/Documents/SOLIDWORKS/SOLIDWORKS 2025/samples/introsw/cabinet_bath.slddrw" --json
sw-cli document export --json "${outdir}/cabinet_bath.PDF"
sw-cli document export --json "${outdir}/cabinet_bath.DWG"
sw-cli document close --discard --json

# Part: export one neutral STEP artifact.
sw-cli document open \
    "${workspace}/users/Public/Documents/SOLIDWORKS/SOLIDWORKS 2025/samples/learn/Paper Airplane.SLDPRT" --json
sw-cli document export --json "${outdir}/Paper Airplane.STEP"
sw-cli document close --discard --json

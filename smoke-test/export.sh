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
swcli document open \
    "${workspace}/Program Files/SOLIDWORKS/sldBenchmarking/Macro/Mold/bezel moldbase.slddrw" --json
swcli document export --json "${outdir}/bezel moldbase.PDF"
swcli document export --json "${outdir}/bezel moldbase.DWG"
swcli document close --discard --json

# Assembly: export one neutral STEP artifact.
swcli document open \
    "${workspace}/Program Files/SOLIDWORKS/sldBenchmarking/Macro/Mold/bezel moldbase.sldasm" --json
swcli document export --json "${outdir}/bezel moldbase.STEP"
swcli document close --discard --json

# Drawing: the DWG exporter may mark the source as modified without saving it.
swcli document open \
    "${workspace}/users/Public/Documents/SOLIDWORKS/SOLIDWORKS 2025/samples/introsw/cabinet_bath.slddrw" --json
swcli document export --json "${outdir}/cabinet_bath.PDF"
swcli document export --json "${outdir}/cabinet_bath.DWG"
swcli document close --discard --json

# Part: export one neutral STEP artifact.
swcli document open \
    "${workspace}/users/Public/Documents/SOLIDWORKS/SOLIDWORKS 2025/samples/learn/Paper Airplane.SLDPRT" --json
swcli document export --json "${outdir}/Paper Airplane.STEP"
swcli document close --discard --json

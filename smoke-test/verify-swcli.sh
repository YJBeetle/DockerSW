#!/usr/bin/env bash
set -Eeuo pipefail

# Host paths/environment belong to DockerSW; CAD assertions belong to SWCLI.
workspace="${1:?usage: verify-swcli.sh WINE_DRIVE_C [OUTPUT_DIRECTORY]}"
modeling_outdir="${2:-$(mktemp -d "${SW_SMOKE_EVIDENCE_DIR:-/tmp}/swcli-generic.XXXXXX")}"
mkdir -p "${modeling_outdir}"
chmod 755 "${modeling_outdir}"
printf '[smoke] Shared modeling evidence: %s\n' "${modeling_outdir}"

part_path="${workspace}/users/Public/Documents/SOLIDWORKS/SOLIDWORKS 2025/samples/learn/Paper Airplane.SLDPRT"
assembly_path="${workspace}/Program Files/SOLIDWORKS/sldBenchmarking/Macro/Mold/bezel moldbase.sldasm"
drawing_path="${workspace}/Program Files/SOLIDWORKS/sldBenchmarking/Macro/Mold/bezel moldbase.slddrw"
# Keep the drawing's relative model references beside its writable test copy.
# Reference models are temporary inputs, not uploaded modeling evidence.
drawing_workdir="$(mktemp -d /tmp/swcli-drawing.XXXXXX)"
trap 'rm -rf -- "${drawing_workdir}"' EXIT
cp -a "$(dirname "${drawing_path}")/." "${drawing_workdir}/"
PYTHONPATH="${SWCLI_SOURCE:-/opt/swcli/src}:${SWCLI_DEPS:-/opt/swcli-deps}/linux" \
    python3 /opt/swcli/scripts/ci/verify-modeling.py \
    --output-dir "${modeling_outdir}" \
    --host-output-dir "$(winepath -w "${modeling_outdir}")" \
    --cli-command /usr/local/bin/sw-cli \
    --sample-part "$(winepath -w "${part_path}")" \
    --sample-assembly "$(winepath -w "${assembly_path}")" \
    --sample-drawing "$(winepath -w "${drawing_path}")" \
    --sample-drawing-local "${drawing_path}" \
    --drawing-work-dir "${drawing_workdir}" \
    --host-drawing-work-dir "$(winepath -w "${drawing_workdir}")"

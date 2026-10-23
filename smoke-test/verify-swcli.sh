#!/usr/bin/env bash
set -Eeuo pipefail

# Host paths/environment belong to DockerSW; CAD assertions belong to SWCLI.
workspace="${1:?usage: verify-swcli.sh WINE_DRIVE_C [OUTPUT_DIRECTORY]}"
modeling_outdir="${2:-$(mktemp -d "${SW_SMOKE_EVIDENCE_DIR:-/tmp}/swcli-generic.XXXXXX")}"
mkdir -p "${modeling_outdir}"
chmod 755 "${modeling_outdir}"
printf '[smoke] Shared isolated functional-set evidence: %s\n' "${modeling_outdir}"

part_path="${workspace}/users/Public/Documents/SOLIDWORKS/SOLIDWORKS 2025/samples/learn/Paper Airplane.SLDPRT"
assembly_path="${workspace}/Program Files/SOLIDWORKS/sldBenchmarking/Macro/Mold/bezel moldbase.sldasm"
drawing_path="${workspace}/Program Files/SOLIDWORKS/sldBenchmarking/Macro/Mold/bezel moldbase.slddrw"
# Keep the drawing's relative model references beside its writable test copy.
# Reference models are temporary inputs, not uploaded modeling evidence.
drawing_workdir="$(mktemp -d /tmp/swcli-drawing.XXXXXX)"
trap 'rm -rf -- "${drawing_workdir}"' EXIT
test -f "${drawing_path}" || { echo 'Installed official drawing fixture is missing' >&2; exit 1; }
drawing_template_args=()
if [[ "${SWCLI_RUNTIME_SUITE:-full}" == full ]]; then
    drawing_template="$(python3 /opt/swcli/scripts/ci/gate_support/drawing_template.py --program-data "${workspace}/ProgramData")"
    drawing_template_args=(--drawing-template "$(winepath -w "${drawing_template}")")
fi
PYTHONPATH="${SWCLI_SOURCE:-/opt/swcli/src}:${SWCLI_DEPS:-/opt/swcli-deps}/linux" \
    python3 /opt/swcli/scripts/ci/verify-runtime-sets.py \
    --suite "${SWCLI_RUNTIME_SUITE:-full}" \
    --mode hidden --wine-prefix "${WINEPREFIX:-/root/.wine}" \
    --output-dir "${modeling_outdir}" \
    --host-output-dir "$(winepath -w "${modeling_outdir}")" \
    --cli-command /usr/local/bin/sw-cli \
    --python-path "${SWCLI_SOURCE:-/opt/swcli/src}" \
    --python-path "${SWCLI_DEPS:-/opt/swcli-deps}/linux" \
    --sample-part "$(winepath -w "${part_path}")" \
    --sample-assembly "$(winepath -w "${assembly_path}")" \
    --sample-drawing "$(winepath -w "${drawing_path}")" \
    --sample-drawing-local "${drawing_path}" \
    --fixture-work-dir "${drawing_workdir}" \
    --host-fixture-work-dir "$(winepath -w "${drawing_workdir}")" \
    "${drawing_template_args[@]}"

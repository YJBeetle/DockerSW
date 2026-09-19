#!/usr/bin/env bash
set -Eeuo pipefail

: "${SW_IMAGE:?SW_IMAGE is required}"

SMOKE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ASSETS_DIR="${SMOKE_DIR}/assets"

smoke_container="sw-cli-export-smoke-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
smoke_root="${RUNNER_TEMP:-${PWD}/.ci-logs}/sw-cli-export-smoke"
output_dir="${smoke_root}/output"
log_file="${smoke_root}/sw-cli-export.log"
export_timeout="${SW_EXPORT_TIMEOUT:-600}"
document_open=false

cleanup() {
    local status=$?
    trap - EXIT
    if [ "${document_open}" = true ]; then
        timeout --foreground 30 \
            docker exec "${smoke_container}" \
            sw-cli document close --discard --json >/dev/null 2>&1 || true
    fi
    timeout --foreground 30 \
        docker exec "${smoke_container}" swclid stop --json >/dev/null 2>&1 || true
    docker rm -f "${smoke_container}" >/dev/null 2>&1 || true
    rm -rf "${ASSETS_DIR}" 2>/dev/null || true
    return "${status}"
}
trap cleanup EXIT

# 准备导出目录。转换策略只有这一个 CI 消费者，因此直接写在本脚本中。
umask 077
rm -rf "${smoke_root}"
mkdir -p "${output_dir}"

echo "[Smoke Test] Creating test container from ${SW_IMAGE}..."
docker create \
    --name "${smoke_container}" \
    --mount "type=bind,source=${smoke_root},target=/ci-smoke" \
    "${SW_IMAGE}" \
    bash -lc 'touch /tmp/dockersw-container-ready; exec sleep infinity' \
    >/dev/null

docker start "${smoke_container}" >/dev/null
for _ in {1..60}; do
    if docker exec "${smoke_container}" \
        test -f /tmp/dockersw-container-ready >/dev/null 2>&1; then
        break
    fi
    sleep 1
done
if ! docker exec "${smoke_container}" \
    test -f /tmp/dockersw-container-ready >/dev/null 2>&1; then
    echo "DockerSW container did not become ready" >&2
    exit 1
fi

workspace=/root/.wine/drive_c
outdir=/ci-smoke/output
deadline=$((SECONDS + export_timeout))

# Keep Docker transport, logging, and the shared deadline out of the example
# workflow below. Every call still maps directly to one `docker exec ... sw-cli`.
run_cli() {
    local remaining=$((deadline - SECONDS))
    local -a pipeline_status
    if [ "${remaining}" -le 0 ]; then
        echo "SOLIDWORKS export smoke test timed out after ${export_timeout} seconds" >&2
        return 1
    fi

    set +e
    timeout --foreground "${remaining}" \
        docker exec "${smoke_container}" sw-cli "$@" 2>&1 \
        | tee -a "${log_file}"
    pipeline_status=("${PIPESTATUS[@]}")
    set -e

    if [ "${pipeline_status[1]}" -ne 0 ]; then
        echo "Failed to write SOLIDWORKS export log" >&2
        return 1
    fi
    case "${pipeline_status[0]}" in
        0)
            ;;
        124)
            echo "SOLIDWORKS export smoke test timed out after ${export_timeout} seconds" >&2
            return 1
            ;;
        *)
            echo "sw-cli failed with status ${pipeline_status[0]}: $*" >&2
            return 1
            ;;
    esac
}

# The export workflow is deliberately explicit so downstream CI users can copy
# it and replace only the source/output paths.

# Drawing: export one PDF and one DWG, then discard SOLIDWORKS' dirty flag.
document_open=true
run_cli document open \
    "${workspace}/Program Files/SOLIDWORKS/sldBenchmarking/Macro/Mold/bezel moldbase.slddrw" --json
run_cli document export "${outdir}/bezel moldbase.PDF" --json
run_cli document export "${outdir}/bezel moldbase.DWG" --allow-source-dirty --json
run_cli document close --discard --json
document_open=false

# Assembly: export one neutral STEP artifact.
document_open=true
run_cli document open \
    "${workspace}/Program Files/SOLIDWORKS/sldBenchmarking/Macro/Mold/bezel moldbase.sldasm" --json
run_cli document export "${outdir}/bezel moldbase.STEP" --json
run_cli document close --discard --json
document_open=false

# Drawing: the DWG exporter may set the source dirty flag without saving it.
document_open=true
run_cli document open \
    "${workspace}/users/Public/Documents/SOLIDWORKS/SOLIDWORKS 2025/samples/introsw/cabinet_bath.slddrw" --json
run_cli document export "${outdir}/cabinet_bath.PDF" --json
run_cli document export "${outdir}/cabinet_bath.DWG" --allow-source-dirty --json
run_cli document close --discard --json
document_open=false

# Part: export one neutral STEP artifact.
document_open=true
run_cli document open \
    "${workspace}/users/Public/Documents/SOLIDWORKS/SOLIDWORKS 2025/samples/learn/Paper Airplane.SLDPRT" --json
run_cli document export "${outdir}/Paper Airplane.STEP" --json
run_cli document close --discard --json
document_open=false

expected_outputs=(
    "bezel moldbase.PDF"
    "bezel moldbase.DWG"
    "bezel moldbase.STEP"
    "cabinet_bath.PDF"
    "cabinet_bath.DWG"
    "Paper Airplane.STEP"
)

for output_name in "${expected_outputs[@]}"; do
    output_path="${output_dir}/${output_name}"
    if [ ! -s "${output_path}" ]; then
        echo "Expected export is missing or empty: ${output_name}" >&2
        exit 1
    fi
    printf '[CI export] verified %s (%s bytes)\n' \
        "${output_name}" "$(stat -c %s "${output_path}")"
done

echo "SOLIDWORKS export smoke test passed: ${#expected_outputs[@]} files verified."

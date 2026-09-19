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

cleanup() {
    local status=$?
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

set +e
timeout --foreground "${export_timeout}" \
    docker exec -i "${smoke_container}" bash -s 2>&1 <<'EXPORT_SCRIPT' \
    | tee "${log_file}"
set -Eeuo pipefail

workspace=/root/.wine/drive_c
outdir=/ci-smoke/output
document_open=false

cleanup_document() {
    if [ "${document_open}" = true ]; then
        sw-cli document close --discard --json >/dev/null 2>&1 || true
    fi
}
trap cleanup_document EXIT

export_document() {
    local source="$1"
    shift
    sw-cli document open "${workspace}/${source}" --json
    document_open=true
    local output
    for output in "$@"; do
        export_args=(document export "${outdir}/${output}" --json)
        if [[ "${output,,}" == *.dwg ]]; then
            export_args+=(--allow-source-dirty)
        fi
        sw-cli "${export_args[@]}"
    done
    sw-cli document close --discard --json
    document_open=false
}

export_document \
    'Program Files/SOLIDWORKS/sldBenchmarking/Macro/Mold/bezel moldbase.slddrw' \
    'bezel moldbase.PDF' 'bezel moldbase.DWG'
export_document \
    'Program Files/SOLIDWORKS/sldBenchmarking/Macro/Mold/bezel moldbase.sldasm' \
    'bezel moldbase.STEP'
export_document \
    'users/Public/Documents/SOLIDWORKS/SOLIDWORKS 2025/samples/introsw/cabinet_bath.slddrw' \
    'cabinet_bath.PDF' 'cabinet_bath.DWG'
export_document \
    'users/Public/Documents/SOLIDWORKS/SOLIDWORKS 2025/samples/learn/Paper Airplane.SLDPRT' \
    'Paper Airplane.STEP'

swclid stop --json
EXPORT_SCRIPT
export_status=${PIPESTATUS[0]}
set -e

case "${export_status}" in
    0)
        ;;
    124)
        echo "SOLIDWORKS export smoke test timed out after ${export_timeout} seconds" >&2
        exit 1
        ;;
    *)
        echo "SOLIDWORKS export smoke test failed with status ${export_status}" >&2
        exit 1
        ;;
esac

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

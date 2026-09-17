#!/usr/bin/env bash
set -Eeuo pipefail

: "${SW_IMAGE:?SW_IMAGE is required}"

SMOKE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ASSETS_DIR="${SMOKE_DIR}/assets"

smoke_container="sw-export-smoke-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
smoke_root="${RUNNER_TEMP:-${PWD}/.ci-logs}/sw-export-smoke"
manifest="${smoke_root}/export-list.txt"
output_dir="${smoke_root}/output"
log_file="${smoke_root}/sw-export.log"
export_timeout="${SW_EXPORT_TIMEOUT:-1800}"

cleanup() {
    local status=$?
    docker rm -f "${smoke_container}" >/dev/null 2>&1 || true
    rm -rf "${ASSETS_DIR}" 2>/dev/null || true
    return "${status}"
}
trap cleanup EXIT

# 准备导出测试清单与目录
umask 077
rm -rf "${smoke_root}"
mkdir -p "${output_dir}"
cat > "${manifest}" <<'EOF'
Program Files/SOLIDWORKS/sldBenchmarking/Macro/Mold/bezel moldbase.slddrw
Program Files/SOLIDWORKS/sldBenchmarking/Macro/Mold/bezel moldbase.sldasm
users/Public/Documents/SOLIDWORKS/SOLIDWORKS 2025/samples/introsw/cabinet_bath.slddrw
users/Public/Documents/SOLIDWORKS/SOLIDWORKS 2025/samples/learn/Paper Airplane.SLDPRT
EOF

echo "[Smoke Test] Creating test container from ${SW_IMAGE}..."
docker create \
    --name "${smoke_container}" \
    --mount "type=bind,source=${smoke_root},target=/ci-smoke" \
    "${SW_IMAGE}" \
    sw-export \
        --list /ci-smoke/export-list.txt \
        --workspace /root/.wine/drive_c \
        --outdir /ci-smoke/output \
    >/dev/null

set +e
timeout --foreground "${export_timeout}" \
    docker start --attach "${smoke_container}" 2>&1 \
    | tee "${log_file}"
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

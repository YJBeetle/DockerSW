#!/usr/bin/env bash
set -Eeuo pipefail

: "${SW_RUNTIME_IMAGE:?SW_RUNTIME_IMAGE is required}"
: "${SW_IMAGE:?SW_IMAGE is required}"
: "${SW_IMAGE_SHA_TAG:?SW_IMAGE_SHA_TAG is required}"
: "${SW_MEDIA_MOUNT:?SW_MEDIA_MOUNT is required}"

install_container="sw-preinstall-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
progress_interval="${SW_PROGRESS_INTERVAL:-300}"
progress_started_at="$(date +%s)"
progress_pid=""
rclone_log_file="${RCLONE_LOG_FILE:-${RUNNER_TEMP:-/tmp}/rclone-gdrive.log}"

stop_progress_heartbeat() {
    if [ -n "${progress_pid}" ]; then
        kill "${progress_pid}" 2>/dev/null || true
        wait "${progress_pid}" 2>/dev/null || true
        progress_pid=""
    fi
}

progress_heartbeat() {
    local now elapsed hours minutes seconds container_state
    while sleep "${progress_interval}"; do
        now="$(date +%s)"
        elapsed="$((now - progress_started_at))"
        hours="$((elapsed / 3600))"
        minutes="$(((elapsed % 3600) / 60))"
        seconds="$((elapsed % 60))"
        if container_state="$(docker inspect --format '{{.State.Status}}' "${install_container}" 2>/dev/null)"; then
            :
        else
            container_state="unavailable"
        fi

        printf '\n[CI progress] elapsed=%02d:%02d:%02d container=%s\n' \
            "${hours}" "${minutes}" "${seconds}" "${container_state}"
        docker stats --no-stream \
            --format '[CI progress] {{.Name}} CPU={{.CPUPerc}} memory={{.MemUsage}}' \
            "${install_container}" 2>/dev/null || true
        df -h / | awk 'NR == 1 || NR == 2 { print "[CI progress] disk " $0 }' || true
        if [ -f "${rclone_log_file}" ]; then
            echo "[CI progress] latest rclone messages:"
            tail -n 5 "${rclone_log_file}" || true
        fi
    done
}

cleanup() {
    local status=$?
    local log_export_dir
    stop_progress_heartbeat
    if [ "${status}" -ne 0 ] && docker inspect "${install_container}" >/dev/null 2>&1; then
        log_export_dir="${RUNNER_TEMP:-${PWD}/.ci-logs}/sw-install-logs"
        umask 077
        mkdir -p "${log_export_dir}"
        docker cp "${install_container}:/var/log/sw-install/." "${log_export_dir}/" \
            >/dev/null 2>&1 || true
    fi
    docker rm -f "${install_container}" >/dev/null 2>&1 || true
    return "${status}"
}
trap cleanup EXIT

test -d "${SW_MEDIA_MOUNT}" || {
    echo "Mounted installation-media directory is missing: ${SW_MEDIA_MOUNT}" >&2
    exit 1
}
test -s "${SW_MEDIA_MOUNT}/swwi/data/solidworks.msi" || {
    echo "SOLIDWORKS MSI is missing from the mounted ISO" >&2
    exit 1
}

docker pull "${SW_RUNTIME_IMAGE}"

docker create \
    --name "${install_container}" \
    --entrypoint /bin/bash \
    --mount "type=bind,source=${SW_MEDIA_MOUNT},target=/mnt/sw-media,readonly" \
    --mount "type=bind,source=${PWD}/assets,target=/mnt/private-assets,readonly" \
    -e SW_INSTALL_TIMEOUT="${SW_INSTALL_TIMEOUT:-10800}" \
    "${SW_RUNTIME_IMAGE}" \
    -Eeuo pipefail -c '
        sw-install \
            --media /mnt/sw-media \
            --registry-dir /mnt/private-assets \
            --accept-eula \
            --log-dir /var/log/sw-install

        sw_program_dir="$(readlink -f "/root/.wine/drive_c/Program Files/SOLIDWORKS Corp/SOLIDWORKS")"
        test -d "${sw_program_dir}"
        test -d "/mnt/private-assets/SOLIDWORKS Corp/SOLIDWORKS"
        case "${sw_program_dir}" in
            "/root/.wine/drive_c/Program Files/"*)
                ;;
            *)
                echo "Unexpected SOLIDWORKS installation path: ${sw_program_dir}" >&2
                exit 1
                ;;
        esac
        cp -a "/mnt/private-assets/SOLIDWORKS Corp/SOLIDWORKS/." "${sw_program_dir}/"

        mkdir -p /opt/sw-preinstalled/flexnet
        cp -a /mnt/private-assets/SolidWorks_Flexnet_Server/. \
            /opt/sw-preinstalled/flexnet/

        test -f "/root/.wine/drive_c/Program Files/SOLIDWORKS Corp/SOLIDWORKS/SLDWORKS.exe"
        test -f /opt/sw-preinstalled/flexnet/lmgrd.exe
        rm -rf /var/log/sw-install
    '

progress_heartbeat &
progress_pid=$!
docker start --attach "${install_container}"
stop_progress_heartbeat

docker commit \
    --change 'LABEL maintainer="YJBeetle"' \
    --change 'LABEL description="Private SolidWorks headless CI container with an internal FlexNet service"' \
    --change 'ENV START_LOCAL_LICENSE=true' \
    --change 'ENV FLEXNET_DIR=/opt/sw-preinstalled/flexnet' \
    --change 'ENV SW_LICENSE_SERVER=' \
    --change 'WORKDIR /workspace' \
    --change 'ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]' \
    --change 'CMD ["sw-export", "--help"]' \
    "${install_container}" "${SW_IMAGE}:${SW_IMAGE_SHA_TAG}"

docker tag "${SW_IMAGE}:${SW_IMAGE_SHA_TAG}" "${SW_IMAGE}:latest"

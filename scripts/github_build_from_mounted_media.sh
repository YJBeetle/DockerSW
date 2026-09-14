#!/usr/bin/env bash
set -Eeuo pipefail

: "${SW_RUNTIME_IMAGE:?SW_RUNTIME_IMAGE is required}"
: "${SW_IMAGE:?SW_IMAGE is required}"
: "${SW_IMAGE_SHA_TAG:?SW_IMAGE_SHA_TAG is required}"
: "${SW_MEDIA_MOUNT:?SW_MEDIA_MOUNT is required}"

install_container="sw-preinstall-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"

cleanup() {
    local status=$?
    local log_export_dir
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

        mkdir -p /opt/sw-preinstalled/flexnet
        cp -a /mnt/private-assets/SolidWorks_Flexnet_Server/. \
            /opt/sw-preinstalled/flexnet/

        test -f "/root/.wine/drive_c/Program Files/SOLIDWORKS Corp/SOLIDWORKS/SLDWORKS.exe"
        test -f /opt/sw-preinstalled/flexnet/lmgrd.exe
        rm -rf /var/log/sw-install
    '

docker start --attach "${install_container}"

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
docker push "${SW_IMAGE}:${SW_IMAGE_SHA_TAG}"
docker push "${SW_IMAGE}:latest"

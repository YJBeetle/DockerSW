#!/usr/bin/env bash
set -euo pipefail

# 仅 -cli 镜像包含此层。安装了 SOLIDWORKS 时预热 SWCLI daemon；
# sw-runtime 没有商业程序，因此直接跳过并保留完整 CLI 客户端能力。
if [ "${SOLIDWORKS_INSTALLED:-false}" != true ]; then
    echo "[DockerSW] 当前镜像未安装 SOLIDWORKS，跳过 SWCLI daemon 预热"
else
    SWCLI_ENDPOINT="${SWCLI_ENDPOINT:-127.0.0.1:18495}"
    SWCLID_START_TIMEOUT="${SWCLID_START_TIMEOUT:-120}"
    VNC_ENABLE="${VNC_ENABLE:-false}"
    if ! [[ "${SWCLID_START_TIMEOUT}" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
        echo "[DockerSW][ERROR] SWCLID_START_TIMEOUT 必须是非负数，当前值: ${SWCLID_START_TIMEOUT}" >&2
        exit 1
    fi
    SWCLID_START_ARGS=(
        daemon start
        --endpoint "${SWCLI_ENDPOINT}"
        --startup-timeout "${SWCLID_START_TIMEOUT}"
        --json
    )
    case "${VNC_ENABLE}" in
        1|true|TRUE|True|yes|YES|Yes|on|ON|On) SWCLID_START_ARGS+=(--visible) ;;
        0|false|FALSE|False|no|NO|No|off|OFF|Off) ;;
        *)
            echo "[DockerSW][ERROR] VNC_ENABLE 必须是 true/false、1/0、yes/no 或 on/off，当前值: ${VNC_ENABLE}" >&2
            exit 1
            ;;
    esac
    echo "[DockerSW] 正在启动并等待 SWCLI daemon 与 SOLIDWORKS 就绪..."
    SWCLID_START_OUTPUT="$(mktemp "${TMPDIR:-/tmp}/swclid-start.XXXXXX")"
    if sw-cli "${SWCLID_START_ARGS[@]}" >"${SWCLID_START_OUTPUT}" 2>&1; then
        if jq -e '.success == true and .result.health.host_connected == true' \
            "${SWCLID_START_OUTPUT}" >/dev/null; then
            rm -f "${SWCLID_START_OUTPUT}"
            echo "[DockerSW] SWCLI daemon 与 SOLIDWORKS 已就绪: ${SWCLI_ENDPOINT}"
        else
            echo "[DockerSW][ERROR] SWCLI daemon 已响应，但 SOLIDWORKS 宿主未连接:" >&2
            cat "${SWCLID_START_OUTPUT}" >&2
            rm -f "${SWCLID_START_OUTPUT}"
            exit 1
        fi
    else
        SWCLID_START_EXIT=$?
        echo "[DockerSW][ERROR] SWCLI daemon 或 SOLIDWORKS 启动失败:" >&2
        cat "${SWCLID_START_OUTPUT}" >&2
        rm -f "${SWCLID_START_OUTPUT}"
        exit "${SWCLID_START_EXIT}"
    fi
fi

if [ "$#" -gt 0 ]; then
    echo "[DockerSW] 容器初始化完成"
    exec "$@"
else
    echo "[DockerSW] 容器就绪。使用 'sw-cli' 执行建模、检查与导出。"
    exec /bin/bash
fi

#!/usr/bin/env bash
set -euo pipefail

# 仅 -cli 镜像包含此层。安装了 SOLIDWORKS 时预热 SWCLI daemon；
# sw-runtime 没有商业程序，因此直接跳过并保留完整 CLI 客户端能力。
if [ "${SOLIDWORKS_INSTALLED:-false}" != true ]; then
    echo "[DockerSW] 当前镜像未安装 SOLIDWORKS，跳过 SWCLI daemon 预热"
else
    SWCLI_ENDPOINT="${SWCLI_ENDPOINT:-127.0.0.1:18495}"
    SWCLID_START_TIMEOUT="${SWCLID_START_TIMEOUT:-120}"
    SWCLID_READY_GRACE="${SWCLID_READY_GRACE:-10}"
    SWCLID_ALLOW_REMOTE="${SWCLID_ALLOW_REMOTE:-false}"
    SWCLID_LOG="${SWCLID_LOG:-/tmp/swclid.log}"
    SWCLID_HOST="${SWCLI_ENDPOINT%:*}"
    SWCLID_PORT="${SWCLI_ENDPOINT##*:}"
    if [ -z "${SWCLID_HOST}" ] || [ "${SWCLID_HOST}" = "${SWCLI_ENDPOINT}" ] || \
       ! [[ "${SWCLID_PORT}" =~ ^[0-9]+$ ]] || \
       ! [[ "${SWCLID_START_TIMEOUT}" =~ ^[0-9]+$ ]] || \
       ! [[ "${SWCLID_READY_GRACE}" =~ ^[0-9]+$ ]]; then
        echo "[DockerSW][ERROR] SWCLI_ENDPOINT 必须为 HOST:PORT，SWCLID_START_TIMEOUT 和 SWCLID_READY_GRACE 必须为整数" >&2
        exit 1
    fi
    SWCLID_SERVE_ARGS=(
        daemon serve
        --host "${SWCLID_HOST}"
        --port "${SWCLID_PORT}"
        --startup-timeout "${SWCLID_START_TIMEOUT}"
    )
    case "${SWCLID_ALLOW_REMOTE,,}" in
        1|true|yes|on) SWCLID_SERVE_ARGS+=(--allow-remote) ;;
        0|false|no|off) ;;
        *)
            echo "[DockerSW][ERROR] SWCLID_ALLOW_REMOTE 必须是 true/false、1/0、yes/no 或 on/off，当前值: ${SWCLID_ALLOW_REMOTE}" >&2
            exit 1
            ;;
    esac
    echo "[DockerSW] 正在启动并等待 SWCLI daemon 与 SOLIDWORKS 就绪..."
    nohup sw-cli "${SWCLID_SERVE_ARGS[@]}" \
        >"${SWCLID_LOG}" 2>&1 &
    SWCLID_PID=$!
    SWCLID_READY=false
    SWCLID_READY_DEADLINE=$((SECONDS + SWCLID_START_TIMEOUT + SWCLID_READY_GRACE))
    while ((SECONDS < SWCLID_READY_DEADLINE)); do
        remaining=$((SWCLID_READY_DEADLINE - SECONDS))
        probe_timeout=3
        if ((remaining < probe_timeout)); then
            probe_timeout=${remaining}
        fi
        if timeout "${probe_timeout}s" sw-cli daemon status \
            --endpoint "${SWCLI_ENDPOINT}" --json >/dev/null 2>&1; then
            SWCLID_READY=true
            break
        fi
        kill -0 "${SWCLID_PID}" 2>/dev/null || break
        sleep 1
    done
    if [ "${SWCLID_READY}" != true ]; then
        echo "[DockerSW][ERROR] SWCLI daemon 未在期限内就绪，请检查 ${SWCLID_LOG}" >&2
        tail -n 100 "${SWCLID_LOG}" >&2 || true
        exit 1
    fi
    echo "[DockerSW] SWCLI daemon 已就绪: ${SWCLI_ENDPOINT}"
fi

if [ "$#" -gt 0 ]; then
    echo "[DockerSW] 容器初始化完成"
    exec "$@"
else
    echo "[DockerSW] 容器就绪。使用 'sw-cli' 执行建模、检查与导出。"
    exec /bin/bash
fi

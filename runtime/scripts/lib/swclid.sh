#!/usr/bin/env bash

swclid_configure() {
    WIN_PYTHON="${SWCLI_WINDOWS_PYTHON:-C:\\Python311\\python.exe}"
    SWCLI_SOURCE="${SWCLI_SOURCE:-/opt/swcli/src}"
    SWCLI_ENDPOINT="${SWCLI_ENDPOINT:-127.0.0.1:18495}"
    SWCLID_LOG="${SWCLID_LOG:-/tmp/swclid.log}"
    SWCLID_START_TIMEOUT="${SWCLID_START_TIMEOUT:-${SWCLI_HOST_START_TIMEOUT:-120}}"
    PYTHONPATH="${SWCLI_SOURCE}${PYTHONPATH:+:${PYTHONPATH}}"
    export PYTHONPATH
}

swclid_ready() {
    python3 -m swcli.daemon status \
        --endpoint "${SWCLI_ENDPOINT}" --json >/dev/null 2>&1
}

swclid_start() {
    local host="${SWCLI_ENDPOINT%:*}"
    local port="${SWCLI_ENDPOINT##*:}"
    if [ -z "${host}" ] || [ "${host}" = "${SWCLI_ENDPOINT}" ] || \
       ! [[ "${host}" =~ ^[A-Za-z0-9._-]+$ ]] || \
       ! [[ "${port}" =~ ^[0-9]+$ ]] || \
       [ "${port}" -lt 1 ] || [ "${port}" -gt 65535 ]; then
        echo "swclid: SWCLI_ENDPOINT must use HOST:PORT" >&2
        return 2
    fi
    if ! [[ "${SWCLID_START_TIMEOUT}" =~ ^[0-9]+$ ]] || \
       [ "${SWCLID_START_TIMEOUT}" -lt 1 ]; then
        echo "swclid: SWCLID_START_TIMEOUT must be a positive integer" >&2
        return 2
    fi

    echo "[DockerSW] Starting resident swclid at ${SWCLI_ENDPOINT}..." >&2
    nohup wine "${WIN_PYTHON}" -m swcli.daemon serve \
        --host "${host}" --port "${port}" --host-platform linux-wine \
        --startup-timeout "${SWCLID_START_TIMEOUT}" \
        >"${SWCLID_LOG}" 2>&1 &

    for ((attempt = 0; attempt < SWCLID_START_TIMEOUT; attempt++)); do
        if swclid_ready; then
            echo "[DockerSW] swclid is ready." >&2
            return 0
        fi
        sleep 1
    done
    echo "[DockerSW][ERROR] swclid did not become ready; log follows:" >&2
    tail -n 100 "${SWCLID_LOG}" >&2 || true
    return 1
}

swclid_ensure() {
    swclid_ready || swclid_start
    export SWCLI_ENDPOINT
}

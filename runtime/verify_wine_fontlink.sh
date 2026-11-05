#!/usr/bin/env bash
set -euo pipefail

probe=${1:?font link probe executable required}
probe_root=$(mktemp -d)
export WINEPREFIX="$probe_root/prefix"
export LOCPATH="$probe_root"
export WINEDLLOVERRIDES='mscoree,mshtml,winemenubuilder.exe='
export DISPLAY=:99

Xvfb "$DISPLAY" -screen 0 1024x768x24 -noreset &
xvfb_pid=$!
trap 'wineserver -k 2>/dev/null || true; kill "$xvfb_pid" 2>/dev/null || true; rm -rf -- "$probe_root"' EXIT
sleep 1
localedef -i zh_CN -f UTF-8 "$LOCPATH/zh_CN.UTF-8"

run_probe() {
    local locale=$1 codepage=$2 output
    shift 2
    if ! output=$(LANG="$locale" LC_ALL="$locale" timeout --foreground 120 wine "$probe" "$@" 2>&1); then
        printf '%s\n' "$output" >&2
        return 1
    fi
    printf '%s\n' "$output"
    grep -q "^ACP=${codepage} " <<< "$output"
}

# Probe writes test values only in the disposable prefix.
snapshot="Z:${probe_root//\//\\}\\fontlinks.bin"
run_probe zh_CN.UTF-8 936 setup-custom "$snapshot"
run_probe C.UTF-8 1252 verify-custom "$snapshot"
run_probe zh_CN.UTF-8 936 setup-default
run_probe C.UTF-8 1252 verify-default

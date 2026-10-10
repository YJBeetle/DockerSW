#!/usr/bin/env bash
# Build-time gate for installed shared engines, not SOLIDWORKS CAD acceptance.
set -Eeuo pipefail
export WINEPREFIX="${WINEPREFIX:-/root/.wine}"
mono_root="${WINEPREFIX}/drive_c/windows/mono/mono-2.0"
probe_source=${1:?CCW probe source required}
probe_root=$(mktemp -d)
trap 'rm -rf -- "${probe_root}"' EXIT
source_windows=$(winepath -w "${probe_source}")
for platform in x86 x64; do
    executable=$(winepath -w "${probe_root}/ccw-${platform}.exe")
    WINE_MONO_AOT=none timeout --foreground 120 wine \
        "${mono_root}/lib/mono/4.5/mcs.exe" "-platform:${platform}" \
        "-out:${executable}" "${source_windows}"
    for mode in none interp; do
        log="${probe_root}/${platform}-${mode}.log"
        if WINE_MONO_AOT="${mode}" timeout --foreground 60 wine "${executable}" > "${log}" 2>&1; then
            cat "${log}"
        else
            result=$?
            cat "${log}" >&2
            exit "${result}"
        fi
        tr -d '\r' < "${log}" > "${log}.normalized"
        grep -Fxq CCW_RELEASE_PROBE_PASS "${log}.normalized"
        test "$(grep -c '=' "${log}.normalized")" -eq 7
        if grep -Eq 'Assertion at|Unhandled Exception|Native Crash Reporting' "${log}"; then
            echo 'CCW probe reported an assertion or exception' >&2
            exit 1
        fi
        printf 'CCW %s %s PASS\n' "${platform}" "${mode}"
    done
done
echo CCW_SHARED_RUNTIME_PASS

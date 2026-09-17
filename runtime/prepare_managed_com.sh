#!/usr/bin/env bash
set -Eeuo pipefail

CONFIG_FILE="${DOCKERSW_MANAGED_COM_CONFIG:-/opt/sw-runtime/managed_com.env}"
# shellcheck source=/dev/null
. "${CONFIG_FILE}"

export WINEPREFIX="${WINEPREFIX:-/root/.wine}"
ASSET_DIR="${DOCKERSW_MANAGED_COM_DIR:-/opt/sw-runtime/managed-com}"
MONO_ROOT="${WINEPREFIX}/drive_c/windows/mono/mono-2.0"

verify_sha256() {
    local file="$1" expected="$2" actual
    [ -f "${file}" ] || {
        echo "Required managed COM file is missing: ${file}" >&2
        exit 1
    }
    actual="$(sha256sum "${file}" | awk '{print $1}')"
    [ "${actual}" = "${expected}" ] || {
        echo "SHA256 mismatch for ${file}: expected ${expected}, got ${actual}" >&2
        exit 1
    }
}

install_verified() {
    local source="$1" destination="$2" expected="$3"
    verify_sha256 "${source}" "${expected}"
    mkdir -p "$(dirname "${destination}")"
    install -m 0644 "${source}" "${destination}"
    verify_sha256 "${destination}" "${expected}"
}

[ -d "${MONO_ROOT}" ] || {
    echo "Wine-Mono ${WINE_MONO_VERSION} is not installed in ${WINEPREFIX}" >&2
    exit 1
}

install_verified "${ASSET_DIR}/libmono-2.0-x86.dll" \
    "${MONO_ROOT}/bin/libmono-2.0-x86.dll" "${MONO_PATCH_SHA256}"
install_verified "${ASSET_DIR}/mscorlib.dll" \
    "${MONO_ROOT}/lib/mono/4.5/mscorlib.dll" "${MONO_MSCORLIB_SHA256}"
install_verified "${ASSET_DIR}/regasm-x86.exe" \
    "${WINEPREFIX}/drive_c/windows/Microsoft.NET/Framework/v4.0.30319/regasm.exe" \
    "${MONO_REGASM_X86_SHA256}"
install_verified "${ASSET_DIR}/regasm-x86_64.exe" \
    "${WINEPREFIX}/drive_c/windows/Microsoft.NET/Framework64/v4.0.30319/regasm.exe" \
    "${MONO_REGASM_X64_SHA256}"
install_verified "${ASSET_DIR}/stdole.dll" \
    "${WINEPREFIX}/drive_c/Program Files/Common Files/SOLIDWORKS Shared/stdole.dll" \
    "${STDOLE_DLL_SHA256}"

echo "Wine ${WINE_VERSION}, Wine-Mono ${WINE_MONO_VERSION}, x86 stdcall and managed COM registration assets are ready."

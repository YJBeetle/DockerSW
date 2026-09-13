#!/usr/bin/env bash
set -Eeuo pipefail

CONFIG_FILE="${DOCKERSW_MANAGED_COM_CONFIG:-/opt/dockersw/managed_com.env}"
# shellcheck source=/dev/null
. "${CONFIG_FILE}"

CACHE_DIR="${DOCKERSW_CACHE_DIR:-/opt/dockersw/cache}"
ASSET_DIR="${DOCKERSW_MANAGED_COM_DIR:-/opt/dockersw/managed-com}"
MONO_MSI="${CACHE_DIR}/wine-mono-${WINE_MONO_VERSION}-x86.msi"
PATCH_BASE_URL="https://github.com/YJBeetle/wine-mono/releases/download/${MONO_PATCH_RELEASE}"
STDOLE_PACKAGE="${CACHE_DIR}/stdole.${STDOLE_VERSION}.nupkg"

verify_sha256() {
    local file="$1" expected="$2" actual
    actual="$(sha256sum "${file}" | awk '{print $1}')"
    [ "${actual}" = "${expected}" ] || {
        echo "SHA256 mismatch for ${file}: expected ${expected}, got ${actual}" >&2
        exit 1
    }
}

download_verified() {
    local label="$1" url="$2" destination="$3" expected="$4"
    echo "[DockerSW Build] Downloading ${label}..."
    curl --fail --location --retry 5 --retry-all-errors --retry-delay 2 \
        --output "${destination}.download" "${url}"
    verify_sha256 "${destination}.download" "${expected}"
    mv "${destination}.download" "${destination}"
}

mkdir -p "${CACHE_DIR}" "${ASSET_DIR}"

download_verified "Wine-Mono ${WINE_MONO_VERSION}" \
    "https://dl.winehq.org/wine/wine-mono/${WINE_MONO_VERSION}/wine-mono-${WINE_MONO_VERSION}-x86.msi" \
    "${MONO_MSI}" "${WINE_MONO_MSI_SHA256}"
download_verified "Wine-Mono x86 stdcall runtime" \
    "${PATCH_BASE_URL}/libmono-2.0-x86.dll" \
    "${ASSET_DIR}/libmono-2.0-x86.dll" "${MONO_PATCH_SHA256}"
download_verified "Wine-Mono RegistrationServices mscorlib" \
    "${PATCH_BASE_URL}/mscorlib.dll" \
    "${ASSET_DIR}/mscorlib.dll" "${MONO_MSCORLIB_SHA256}"
download_verified "Wine-Mono x86 RegAsm" \
    "${PATCH_BASE_URL}/regasm-x86.exe" \
    "${ASSET_DIR}/regasm-x86.exe" "${MONO_REGASM_X86_SHA256}"
download_verified "Wine-Mono x64 RegAsm" \
    "${PATCH_BASE_URL}/regasm-x86_64.exe" \
    "${ASSET_DIR}/regasm-x86_64.exe" "${MONO_REGASM_X64_SHA256}"
download_verified "Microsoft stdole ${STDOLE_VERSION}" \
    "https://api.nuget.org/v3-flatcontainer/stdole/${STDOLE_VERSION}/stdole.${STDOLE_VERSION}.nupkg" \
    "${STDOLE_PACKAGE}" "${STDOLE_PACKAGE_SHA256}"

rm -f "${ASSET_DIR}/stdole.dll.download"
7z e -so "${STDOLE_PACKAGE}" 'lib/net10/stdole.dll' >"${ASSET_DIR}/stdole.dll.download"
verify_sha256 "${ASSET_DIR}/stdole.dll.download" "${STDOLE_DLL_SHA256}"
mv "${ASSET_DIR}/stdole.dll.download" "${ASSET_DIR}/stdole.dll"
rm -f "${STDOLE_PACKAGE}"

echo "[DockerSW Build] Managed COM assets verified."

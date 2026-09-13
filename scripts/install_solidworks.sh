#!/usr/bin/env bash
set -Eeuo pipefail

PROGRAM_NAME="dockersw-install"
MEDIA_PATH="${SW_MEDIA_PATH:-}"
REGISTRY_DIR="${SW_INSTALL_REGISTRY_DIR:-}"
MSI_RELATIVE_PATH="${SW_MSI_RELATIVE_PATH:-swwi/data/solidworks.msi}"
LOG_DIR="${SW_INSTALL_LOG_DIR:-/var/log/dockersw-install}"
INSTALL_TIMEOUT="${SW_INSTALL_TIMEOUT:-10800}"
VALIDATE_ONLY=false
INSTALL_WPF_THEMES="${SW_INSTALL_WPF_THEMES:-true}"
MSI_PROPERTIES=()
TEMP_DIRS=()
XVFB_PID=""

usage() {
    cat <<'EOF'
Usage:
  dockersw-install --media PATH [options]

Required:
  --media PATH             Complete official SOLIDWORKS media directory or archive.

Options:
  --registry-dir PATH      Import every .reg file in PATH before installation.
  --msi PATH               MSI path relative to the media root.
                           Default: swwi/data/solidworks.msi
  --property NAME=VALUE    Additional MSI property; may be repeated.
  --log-dir PATH           Protected installation log directory.
  --timeout SECONDS        Timeout for each long-running installer operation.
  --validate-only          Validate/extract the media without running Wine.
  -h, --help               Show this help.

Environment equivalents:
  SW_MEDIA_PATH, SW_INSTALL_REGISTRY_DIR, SW_MSI_RELATIVE_PATH,
  SW_MSI_PROPERTIES_FILE, SW_INSTALL_LOG_DIR, SW_INSTALL_TIMEOUT,
  SW_INSTALL_WPF_THEMES, WINEPREFIX.

The MSI log can contain serial-number properties. Keep the log directory private.
EOF
}

die() {
    echo "[DockerSW Install][ERROR] $*" >&2
    exit 1
}

info() {
    echo "[DockerSW Install] $*"
}

cleanup() {
    if [ -n "${XVFB_PID}" ]; then
        kill "${XVFB_PID}" 2>/dev/null || true
        wait "${XVFB_PID}" 2>/dev/null || true
    fi
    local directory
    for directory in ${TEMP_DIRS[@]+"${TEMP_DIRS[@]}"}; do
        [ -n "${directory}" ] && rm -rf -- "${directory}"
    done
    return 0
}
trap cleanup EXIT

while [ "$#" -gt 0 ]; do
    case "$1" in
        --media)
            [ "$#" -ge 2 ] || die "--media requires a path"
            MEDIA_PATH="$2"
            shift 2
            ;;
        --registry-dir)
            [ "$#" -ge 2 ] || die "--registry-dir requires a path"
            REGISTRY_DIR="$2"
            shift 2
            ;;
        --msi)
            [ "$#" -ge 2 ] || die "--msi requires a relative path"
            MSI_RELATIVE_PATH="$2"
            shift 2
            ;;
        --property)
            [ "$#" -ge 2 ] || die "--property requires NAME=VALUE"
            [[ "$2" == *=* ]] || die "invalid MSI property (expected NAME=VALUE)"
            MSI_PROPERTIES+=("$2")
            shift 2
            ;;
        --log-dir)
            [ "$#" -ge 2 ] || die "--log-dir requires a path"
            LOG_DIR="$2"
            shift 2
            ;;
        --timeout)
            [ "$#" -ge 2 ] || die "--timeout requires seconds"
            INSTALL_TIMEOUT="$2"
            shift 2
            ;;
        --validate-only)
            VALIDATE_ONLY=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "unknown argument: $1"
            ;;
    esac
done

[ -n "${MEDIA_PATH}" ] || die "--media or SW_MEDIA_PATH is required"
[ -e "${MEDIA_PATH}" ] || die "media path does not exist: ${MEDIA_PATH}"
[[ "${INSTALL_TIMEOUT}" =~ ^[1-9][0-9]*$ ]] || die "timeout must be a positive integer"

if [ -n "${SW_MSI_PROPERTIES_FILE:-}" ]; then
    [ -f "${SW_MSI_PROPERTIES_FILE}" ] || die "MSI properties file does not exist"
    while IFS= read -r property || [ -n "${property}" ]; do
        property="${property%$'\r'}"
        [ -z "${property}" ] && continue
        [[ "${property}" == \#* ]] && continue
        [[ "${property}" == *=* ]] || die "invalid line in MSI properties file"
        MSI_PROPERTIES+=("${property}")
    done < "${SW_MSI_PROPERTIES_FILE}"
fi

prepare_media() {
    local source="$1"
    if [ -d "${source}" ]; then
        MEDIA_CONTAINER="${source}"
        return
    fi

    local destination
    destination="$(mktemp -d /tmp/dockersw-media.XXXXXX)"
    TEMP_DIRS+=("${destination}")
    info "Extracting the private installation-media archive..." >&2

    # GNU tar can mistake the leading zero blocks in an ISO image for an empty
    # tar archive and return success. Let 7-Zip identify arbitrary media first;
    # keep tar only as a fallback for environments without a capable 7-Zip.
    if command -v 7z >/dev/null 2>&1 && 7z t "${source}" >/dev/null 2>&1; then
        7z x -y -o"${destination}" "${source}" >/dev/null
    elif tar -tf "${source}" >/dev/null 2>&1; then
        tar -xf "${source}" -C "${destination}"
    else
        die "installation media is not a supported archive or ISO image"
    fi
    MEDIA_CONTAINER="${destination}"
}

MEDIA_CONTAINER=""
prepare_media "${MEDIA_PATH}"
MSI_PATH=""

if [ -f "${MEDIA_CONTAINER}/${MSI_RELATIVE_PATH}" ]; then
    MEDIA_ROOT="${MEDIA_CONTAINER}"
    MSI_PATH="${MEDIA_ROOT}/${MSI_RELATIVE_PATH}"
else
    MSI_PATH="$(find "${MEDIA_CONTAINER}" -type f -ipath "*/${MSI_RELATIVE_PATH}" -print -quit)"
    [ -n "${MSI_PATH}" ] || die "official MSI not found: ${MSI_RELATIVE_PATH}"
    MEDIA_ROOT="${MSI_PATH%/${MSI_RELATIVE_PATH}}"
fi

VC_INSTALLER="${MEDIA_ROOT}/PreReqs/VCRedist17/VC_redist.x64.exe"
LOGIN_MANAGER_INSTALLER="${MEDIA_ROOT}/swloginmgr/SOLIDWORKS Login Manager.msi"
[ -s "${MSI_PATH}" ] || die "SOLIDWORKS MSI is empty"
[ -s "${VC_INSTALLER}" ] || die "official VC++ x64 prerequisite is missing"
[ -s "${LOGIN_MANAGER_INSTALLER}" ] || die "official SOLIDWORKS Login Manager MSI is missing"

info "Validated complete media layout and official prerequisite files."
if [ "${VALIDATE_ONLY}" = true ]; then
    exit 0
fi

for command_name in wine wineboot wineserver winepath timeout Xvfb; do
    command -v "${command_name}" >/dev/null 2>&1 || die "required command is unavailable: ${command_name}"
done

export WINEARCH="${WINEARCH:-win64}"
export WINEPREFIX="${WINEPREFIX:-/root/.wine}"
export WINEDEBUG="${WINEDEBUG:--all}"
export DISPLAY="${DISPLAY:-:99}"

umask 077
mkdir -p "${LOG_DIR}"

start_xvfb() {
    local screen_number socket attempt
    screen_number="$(printf '%s' "${DISPLAY}" | sed -E 's/.*:([0-9]+).*/\1/')"
    socket="/tmp/.X11-unix/X${screen_number}"
    if [ -S "${socket}" ]; then
        return
    fi
    Xvfb "${DISPLAY}" -screen 0 1280x1024x24 -ac +extension GLX +render -noreset \
        >"${LOG_DIR}/xvfb.log" 2>&1 &
    XVFB_PID=$!
    for attempt in $(seq 1 50); do
        [ -S "${socket}" ] && return
        kill -0 "${XVFB_PID}" 2>/dev/null || die "Xvfb exited before becoming ready"
        sleep 0.2
    done
    die "Xvfb did not become ready"
}

run_installer() {
    local label="$1"
    shift
    local status
    info "Running ${label}; details are written to the protected log directory."
    set +e
    timeout --foreground "${INSTALL_TIMEOUT}" "$@"
    status=$?
    set -e
    case "${status}" in
        0|102|194)
            return 0
            ;;
        124)
            die "${label} timed out after ${INSTALL_TIMEOUT} seconds"
            ;;
        *)
            die "${label} failed with exit status ${status}; inspect ${LOG_DIR}"
            ;;
    esac
}

has_msi_property() {
    local expected="$1" property
    for property in "${MSI_PROPERTIES[@]}"; do
        if [ "${property%%=*}" = "${expected}" ]; then
            return 0
        fi
    done
    return 1
}

append_default_msi_property() {
    local name="$1" value="$2"
    has_msi_property "${name}" || MSI_PROPERTIES+=("${name}=${value}")
}

start_xvfb

if [ ! -s "${WINEPREFIX}/system.reg" ]; then
    info "Creating a clean Wine prefix with Mono/Gecko autoload disabled."
    mkdir -p "${WINEPREFIX}"
    run_installer "wineboot" env WINEDLLOVERRIDES="mscoree,mshtml=" wineboot -u
    timeout --foreground 300 wineserver -w || die "wineserver did not settle after wineboot"
fi

run_installer "Wine prefix probe" wine cmd /c ver

MONO_ROOT="${WINEPREFIX}/drive_c/windows/mono/mono-2.0"
if [ ! -d "${MONO_ROOT}" ]; then
    MONO_INSTALLER="$(find /opt/dockersw/cache -maxdepth 1 -type f -name 'wine-mono*.msi' -print -quit 2>/dev/null || true)"
    [ -n "${MONO_INSTALLER}" ] && [ -f "${MONO_INSTALLER}" ] \
        || die "Wine-Mono is not installed and the verified installer cache is missing"
    run_installer "Wine-Mono" env WINEDLLOVERRIDES="mshtml=" \
        wine msiexec /i "${MONO_INSTALLER}" /quiet /norestart
    timeout --foreground 300 wineserver -w || die "wineserver did not settle after Wine-Mono installation"
fi

[ -x /usr/local/lib/dockersw/prepare_managed_com.sh ] \
    || die "managed COM preparation helper is unavailable"
info "Preparing the verified Wine-Mono stdcall and managed COM registration runtime."
/usr/local/lib/dockersw/prepare_managed_com.sh

if [ -n "${REGISTRY_DIR}" ]; then
    [ -d "${REGISTRY_DIR}" ] || die "registry directory does not exist"
    while IFS= read -r -d '' registry_file; do
        info "Importing private installer registry file: $(basename "${registry_file}")"
        run_installer "registry import" wine regedit /S "${registry_file}"
    done < <(find "${REGISTRY_DIR}" -maxdepth 1 -type f -iname '*.reg' -print0 | sort -z)
fi

VC_LOG_WINDOWS="$(winepath -w "${LOG_DIR}/vcredist-x64.log")"
run_installer "Microsoft VC++ x64 prerequisite" \
    wine "${VC_INSTALLER}" /install /quiet /norestart /log "${VC_LOG_WINDOWS}"

VC_LIBRARIES=(
    concrt140 msvcp140 msvcp140_1 msvcp140_2 msvcp140_atomic_wait
    msvcp140_codecvt_ids vcruntime140 vcruntime140_1 vcomp140 mfc140u
)
for library in "${VC_LIBRARIES[@]}"; do
    find "${WINEPREFIX}/drive_c/windows/system32" -maxdepth 1 -type f -iname "${library}.dll" -print -quit | grep -q . \
        || die "VC++ prerequisite completed but ${library}.dll is missing"
done

LOGIN_MANAGER_LOG_WINDOWS="$(winepath -w "${LOG_DIR}/login-manager-install.log")"
run_installer "SOLIDWORKS Login Manager MSI" \
    wine msiexec /i "${LOGIN_MANAGER_INSTALLER}" /qn /norestart DISABLEROLLBACK=1 \
    /l*v "${LOGIN_MANAGER_LOG_WINDOWS}"
timeout --foreground 300 wineserver -w || die "wineserver did not settle after Login Manager installation"

LOGIN_MANAGER_DLL="${WINEPREFIX}/drive_c/Program Files/Common Files/SOLIDWORKS Shared/LoginManager/sldLoginManager.dll"
[ -s "${LOGIN_MANAGER_DLL}" ] \
    || die "Login Manager installer exited successfully but sldLoginManager.dll is missing"

LOGIN_MANAGER_CLSID='{69EF7FA2-6705-47CF-AA78-2E4264D24EB3}'
LOGIN_MANAGER_REGISTRY="$(wine reg query "HKCR\\CLSID\\${LOGIN_MANAGER_CLSID}\\InprocServer32" /s 2>/dev/null || true)"
printf '%s' "${LOGIN_MANAGER_REGISTRY}" | grep -Fqi 'mscoree.dll' \
    || die "Login Manager COM registration is missing the mscoree.dll host"
printf '%s' "${LOGIN_MANAGER_REGISTRY}" | grep -Fqi 'sldLoginManager.LoginManager' \
    || die "Login Manager COM registration is missing its managed class"
printf '%s' "${LOGIN_MANAGER_REGISTRY}" | grep -Fqi 'sldLoginManager.dll' \
    || die "Login Manager COM registration is missing the assembly CodeBase"
info "Verified real SOLIDWORKS Login Manager managed COM registration."

# SOLIDWORKS' quiet-mode custom action does not reliably select the core
# feature under Wine when msiexec is invoked with only generic MSI switches.
# Pass the documented command-line deployment properties explicitly. Callers
# can still override every default with --property or SW_MSI_PROPERTIES_FILE.
# Do not pass the package's default INSTALLDIR: Wine releases before the 2026
# msiexec quoting fix can reject properties containing spaces with MSI 1639.
append_default_msi_property "ENABLEPERFORMANCE" "0"
append_default_msi_property "OFFICEOPTION" "3"
append_default_msi_property "ADDLOCAL" "SolidWorks"

MSI_LOG_WINDOWS="$(winepath -w "${LOG_DIR}/solidworks-msi.log")"
MSI_ARGUMENTS=(
    msiexec /i "${MSI_PATH}" /qb /norestart DISABLEROLLBACK=1
    /l*v "${MSI_LOG_WINDOWS}"
)
MSI_ARGUMENTS+=("${MSI_PROPERTIES[@]}")
run_installer "SOLIDWORKS MSI" wine "${MSI_ARGUMENTS[@]}"
timeout --foreground 600 wineserver -w || die "wineserver did not settle after SOLIDWORKS installation"

SW_EXE="$(find "${WINEPREFIX}/drive_c" -type f -iname SLDWORKS.exe -print -quit)"
[ -n "${SW_EXE}" ] || die "installer returned success but SLDWORKS.exe was not found"

install_wpf_themes() {
    [ "${INSTALL_WPF_THEMES}" = true ] || return
    command -v 7z >/dev/null 2>&1 || die "7z is required to extract WPF themes"
    local dotnet temp mzz system_wpf source_name theme filename
    dotnet="${MEDIA_ROOT}/PreReqs/dotNetFx/ndp48-x86-x64-allos-enu.exe"
    [ -s "${dotnet}" ] || die "official .NET 4.8 prerequisite is missing; cannot extract WPF themes"
    temp="$(mktemp -d /tmp/dockersw-wpf.XXXXXX)"
    TEMP_DIRS+=("${temp}")
    7z e -y -o"${temp}" "${dotnet}" netfx_Full.mzz >>"${LOG_DIR}/wpf-themes.log" 2>&1
    mzz="${temp}/netfx_Full.mzz"
    [ -s "${mzz}" ] || die "netfx_Full.mzz was not found in the official .NET package"
    7z e -y -o"${temp}" "${mzz}" \
        PresentationFramework.Luna_amd64.dll \
        PresentationFramework.Aero_amd64.dll \
        PresentationFramework.Classic_amd64.dll \
        PresentationFramework.Royale_amd64.dll \
        PresentationFramework.AeroLite.dll_amd64 \
        >>"${LOG_DIR}/wpf-themes.log" 2>&1
    system_wpf="${WINEPREFIX}/drive_c/windows/Microsoft.NET/Framework64/v4.0.30319/WPF"
    mkdir -p "${system_wpf}"
    while IFS='|' read -r theme source_name; do
        filename="PresentationFramework.${theme}.dll"
        [ -s "${temp}/${source_name}" ] || die "WPF theme payload is missing: ${source_name}"
        cp "${temp}/${source_name}" "$(dirname "${SW_EXE}")/${filename}"
        cp "${temp}/${source_name}" "${system_wpf}/${filename}"
    done <<'EOF'
Luna|PresentationFramework.Luna_amd64.dll
Aero|PresentationFramework.Aero_amd64.dll
Classic|PresentationFramework.Classic_amd64.dll
Royale|PresentationFramework.Royale_amd64.dll
AeroLite|PresentationFramework.AeroLite.dll_amd64
EOF
}

install_wpf_themes

CANONICAL_SW_DIR="${WINEPREFIX}/drive_c/Program Files/SOLIDWORKS Corp/SOLIDWORKS"
ACTUAL_SW_DIR="$(dirname "${SW_EXE}")"
if [ "${ACTUAL_SW_DIR}" != "${CANONICAL_SW_DIR}" ]; then
    mkdir -p "$(dirname "${CANONICAL_SW_DIR}")"
    rm -rf -- "${CANONICAL_SW_DIR}"
    ln -s "${ACTUAL_SW_DIR}" "${CANONICAL_SW_DIR}"
fi

chmod -R go-rwx "${LOG_DIR}" 2>/dev/null || true
info "SOLIDWORKS installation completed and SLDWORKS.exe was verified."
info "Installation logs remain private at ${LOG_DIR}."

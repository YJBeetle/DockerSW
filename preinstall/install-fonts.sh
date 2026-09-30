#!/usr/bin/env bash
set -Eeuo pipefail

if [ "$#" -ne 3 ]; then
    echo "Usage: install-fonts.sh SOURCE_DIR MANIFEST CATEGORY" >&2
    exit 2
fi

source_dir="$1"
manifest="$2"
category="$3"
windows_fonts="${WINEPREFIX:-/root/.wine}/drive_c/windows/Fonts"
fonts_key='HKLM\Software\Microsoft\Windows NT\CurrentVersion\Fonts'

test -d "${source_dir}" || {
    echo "[DockerSW][ERROR] 字体目录不存在: ${source_dir}" >&2
    exit 1
}
test -s "${manifest}" || {
    echo "[DockerSW][ERROR] 字体清单不存在或为空: ${manifest}" >&2
    exit 1
}

install -d -m 0755 "${windows_fonts}"
installed=0
while IFS=$'\t' read -r file_name registry_name; do
    case "${file_name}" in
        ''|'#'*) continue ;;
    esac
    source_file="${source_dir}/${file_name}"
    test -s "${source_file}" || {
        echo "[DockerSW][ERROR] 缺少字体文件: ${source_file}" >&2
        exit 1
    }

    install -m 0644 "${source_file}" "${windows_fonts}/${file_name}"
    wine reg add "${fonts_key}" /v "${registry_name}" /t REG_SZ /d "${file_name}" /f >/dev/null
    installed=$((installed + 1))
done < "${manifest}"

test "${installed}" -gt 0 || {
    echo "[DockerSW][ERROR] 字体清单没有可安装条目: ${manifest}" >&2
    exit 1
}

wineserver -k || true
wineserver -w
echo "[DockerSW] 已安装 ${category} 字体文件: ${installed} 个"

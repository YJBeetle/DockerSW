#!/usr/bin/env bash
set -euo pipefail

export WINEARCH="win64"
export WINEPREFIX="${WINEPREFIX:-/root/.wine}"
export WINEDEBUG="${WINEDEBUG:--all}"
export DISPLAY="${DISPLAY:-:99}"

export SW_INSTALL_DIR="${SW_INSTALL_DIR:-/opt/solidworks}"
export SW_PROGRAMDATA="${SW_PROGRAMDATA:-/opt/solidworks_programdata}"
export FLEXNET_DIR="${FLEXNET_DIR:-/opt/SolidWorks_Flexnet_Server}"
export START_LOCAL_LICENSE="${START_LOCAL_LICENSE:-false}"
export SW_LICENSE_SERVER="${SW_LICENSE_SERVER:-}"

export WINEDLLOVERRIDES="concrt140=n,b;msvcp140=n,b;msvcp140_1=n,b;msvcp140_2=n,b;msvcp140_atomic_wait=n,b;msvcp140_codecvt_ids=n,b;vcruntime140=n,b;vcruntime140_1=n,b;vcomp140=n,b;mfc140u=n,b;d3dcompiler_47=n,b;d3d11=n,b;dxgi=n,b"

echo "========================================================="
echo "  DockerSW Headless Container (Wine SolidWorks Runtime)  "
echo "========================================================="

# 1. 守护启动 Xvfb 无头虚拟显示服务（COM 消息循环必需）
SCREEN_NUM=$(echo "${DISPLAY}" | sed -E 's/.*:([0-9]+).*/\1/')
if [ ! -S "/tmp/.X11-unix/X${SCREEN_NUM}" ]; then
    echo "[DockerSW] 正在拉起 Xvfb 虚拟屏幕 (${DISPLAY})..."
    Xvfb "${DISPLAY}" -screen 0 1024x768x24 -ac +extension GLX +render -noreset >/dev/null 2>&1 &
    XVFB_PID=$!
    for _ in {1..20}; do
        if [ -S "/tmp/.X11-unix/X${SCREEN_NUM}" ]; then
            break
        fi
        sleep 0.2
    done
    echo "[DockerSW] Xvfb 虚拟屏幕 (${DISPLAY}) 已就绪 (PID: ${XVFB_PID})"
else
    echo "[DockerSW] 已检测到现有 X11 服务 (${DISPLAY})"
fi

# 2. 注入 VC++ / MFC 原生运行库动态链接库（若提供）
VC_DLLS_DIR="${VC_DLLS_DIR:-/opt/vc_redist_dlls}"
if [ -d "${VC_DLLS_DIR}" ]; then
    echo "[DockerSW] 正在注入 VC++ / MFC 运行库动态链接库..."
    cp -n "${VC_DLLS_DIR}"/*.dll "${WINEPREFIX}/drive_c/windows/system32/" 2>/dev/null || true
fi

# 3. 自动检测并安装 Wine-Mono，然后校验/配置 stdcall 与托管 COM 注册组件。
# 这也覆盖用户挂载一个全新 WINEPREFIX 的场景。
MONO_ROOT="${WINEPREFIX}/drive_c/windows/mono/mono-2.0"
if [ ! -d "${MONO_ROOT}" ]; then
    MONO_MSI=$(find /opt/sw-runtime/cache -maxdepth 1 -type f -name 'wine-mono*.msi' -print -quit 2>/dev/null || true)
    if [ -z "${MONO_MSI}" ] || [ ! -f "${MONO_MSI}" ]; then
        echo "[DockerSW][ERROR] 未找到内置 Wine-Mono 安装包" >&2
        exit 1
    fi
    echo "[DockerSW] 正在静默安装 Wine-Mono 运行库 (${MONO_MSI})..."
    WINEDLLOVERRIDES="mshtml=" wine msiexec /i "${MONO_MSI}" /quiet /norestart
    wineserver -w
fi

echo "[DockerSW] 正在校验 Wine-Mono stdcall 与托管 COM 注册组件..."
/usr/local/lib/sw-runtime/prepare_managed_com.sh

# 4. 映射或验证 SolidWorks 程序目录
C_SW_CORP="${WINEPREFIX}/drive_c/Program Files/SOLIDWORKS Corp"
C_SW_TARGET="${C_SW_CORP}/SOLIDWORKS"
mkdir -p "${C_SW_CORP}"

if [ -d "${SW_INSTALL_DIR}" ] && [ "${SW_INSTALL_DIR}" != "${C_SW_TARGET}" ]; then
    SW_SOURCE_REAL="$(readlink -f "${SW_INSTALL_DIR}")"
    SW_TARGET_REAL="$(readlink -f "${C_SW_TARGET}" 2>/dev/null || true)"
    if [ -n "${SW_TARGET_REAL}" ] && [ "${SW_SOURCE_REAL}" = "${SW_TARGET_REAL}" ]; then
        echo "[DockerSW] 使用已映射的 SolidWorks 目录: ${C_SW_TARGET}"
    else
        echo "[DockerSW] 映射 SolidWorks 目录: ${SW_INSTALL_DIR} -> ${C_SW_TARGET}"
        rm -rf "${C_SW_TARGET}"
        ln -sfn "${SW_INSTALL_DIR}" "${C_SW_TARGET}"
    fi
elif [ -d "${C_SW_TARGET}" ]; then
    echo "[DockerSW] 使用内置 SolidWorks 目录: ${C_SW_TARGET}"
fi

if [ -f "${C_SW_TARGET}/SLDWORKS.exe" ]; then
    echo "[DockerSW] 验证主程序: SLDWORKS.exe 存在"
    (
        cd "${C_SW_TARGET}"
        for dll in sldshellutils.dll sldsearchcore.dll; do
            if [ -f "${dll}" ]; then
                wine regsvr32 /s "${dll}" >/dev/null 2>&1 || true
            fi
        done
    )
else
    echo "[DockerSW][WARN] 未检测到 SLDWORKS.exe"
fi

# 自动扫描并导入 SolidWorks 注册表文件
SW_REG_SEARCH_DIRS=("/opt/solidworks_reg" "/opt/solidworks_c" "${SW_INSTALL_DIR}")
for reg_dir in "${SW_REG_SEARCH_DIRS[@]}"; do
    if [ -d "${reg_dir}" ]; then
        for reg_file in "${reg_dir}"/*.reg; do
            if [ -f "${reg_file}" ]; then
                echo "[DockerSW] 正在导入 SolidWorks 注册表: ${reg_file}..."
                wine reg import "${reg_file}" >/dev/null 2>&1 || true
            fi
        done
    fi
done

# 映射 ProgramData（如果提供）
if [ -d "${SW_PROGRAMDATA}" ]; then
    C_PD_TARGET="${WINEPREFIX}/drive_c/ProgramData/SOLIDWORKS"
    mkdir -p "${WINEPREFIX}/drive_c/ProgramData"
    rm -rf "${C_PD_TARGET}"
    ln -sfn "${SW_PROGRAMDATA}" "${C_PD_TARGET}"
fi

# 5. 如果是构建期 --init-only，刷新注册表并安全退出
if [ "${1:-}" = "--init-only" ]; then
    echo "[DockerSW] 正在持久化 Wine 注册表与系统配置..."
    wineserver -w || true
    if [ -n "${XVFB_PID:-}" ]; then
        kill "${XVFB_PID}" 2>/dev/null || true
        wait "${XVFB_PID}" 2>/dev/null || true
    fi
    rm -rf /tmp/.X11-unix /tmp/* 2>/dev/null || true
    echo "[DockerSW] 无头运行环境构建预热完成 (--init-only)"
    exit 0
fi

# 6. 许可服务器配置与管理（运行时）
configure_license_server() {
    local address="$1"
    wine reg add 'HKLM\SOFTWARE\FLEXlm License Manager' /v SW_D_LICENSE_FILE /t REG_SZ /d "${address}" /f >/dev/null
    wine reg add 'HKCU\SOFTWARE\FLEXlm License Manager' /v SW_D_LICENSE_FILE /t REG_SZ /d "${address}" /f >/dev/null
    wine reg add 'HKLM\System\CurrentControlSet\Control\Session Manager\Environment' /v SOLIDWORKS_LICENSE_FILE /t REG_SZ /d "${address}" /f >/dev/null
    wine reg add 'HKLM\System\CurrentControlSet\Control\Session Manager\Environment' /v SW_D_LICENSE_FILE /t REG_SZ /d "${address}" /f >/dev/null
    export SOLIDWORKS_LICENSE_FILE="${address}"
    export SW_D_LICENSE_FILE="${address}"
}

if [ -n "${SW_LICENSE_SERVER}" ]; then
    echo "[DockerSW] 配置远程许可服务器: ${SW_LICENSE_SERVER}"
    configure_license_server "${SW_LICENSE_SERVER}"
elif [ "${START_LOCAL_LICENSE}" = "true" ]; then
    [ -f "${FLEXNET_DIR}/lmgrd.exe" ] || {
        echo "[DockerSW][ERROR] 已启用本地许可服务，但缺少 ${FLEXNET_DIR}/lmgrd.exe" >&2
        exit 1
    }
    echo "[DockerSW] 正在启动容器内本地 FlexNet 许可服务守护 (lmgrd.exe)..."
    LIC_FILE="${FLEXNET_DIR}/sw_d_SSQ.lic"
    if [ ! -f "${LIC_FILE}" ]; then
        LIC_FILE=$(find "${FLEXNET_DIR}" -maxdepth 1 -type f -name '*.lic' -print -quit)
    fi
    [ -n "${LIC_FILE}" ] && [ -f "${LIC_FILE}" ] || {
        echo "[DockerSW][ERROR] 已启用本地许可服务，但未找到 .lic 文件" >&2
        exit 1
    }

    (
        cd "${FLEXNET_DIR}"
        nohup wine "${FLEXNET_DIR}/lmgrd.exe" -c "${LIC_FILE}" -l /tmp/flexnet.log >/dev/null 2>&1 &
    )

    LOCAL_LICENSE_ADDRESS="25734@127.0.0.1"
    configure_license_server "${LOCAL_LICENSE_ADDRESS}"

    if [ -f "${FLEXNET_DIR}/lmutil.exe" ]; then
        LICENSE_READY=false
        for _ in $(seq 1 30); do
            if timeout --foreground 5 wine "${FLEXNET_DIR}/lmutil.exe" lmstat -a -c "${LOCAL_LICENSE_ADDRESS}" >/dev/null 2>&1; then
                LICENSE_READY=true
                break
            fi
            sleep 1
        done
        [ "${LICENSE_READY}" = true ] || {
            echo "[DockerSW][ERROR] 本地 FlexNet 服务未在期限内就绪，请检查 /tmp/flexnet.log" >&2
            exit 1
        }
    fi
    echo "[DockerSW] 本地 FlexNet 服务已就绪: ${LOCAL_LICENSE_ADDRESS}"
else
    echo "[DockerSW][WARN] 未配置 SW_LICENSE_SERVER，且本地许可服务未启用"
fi

# 7. 执行传入命令或进入交互终端
if [ "$#" -gt 0 ]; then
    echo "[DockerSW] 执行指令: $@"
    exec "$@"
else
    echo "[DockerSW] 容器就绪。可以通过 'sw-export' 命令进行批量文件导出。"
    exec /bin/bash
fi

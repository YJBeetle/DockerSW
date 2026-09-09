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
    # 等待 X11 套接字生成
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

# 2. 注入 VC++ / MFC 原生运行库动态链接库（若挂载提供）
VC_DLLS_DIR="${VC_DLLS_DIR:-/opt/vc_redist_dlls}"
if [ -d "${VC_DLLS_DIR}" ]; then
    echo "[DockerSW] 正在注入 VC++ / MFC 运行库动态链接库..."
    cp -n "${VC_DLLS_DIR}"/*.dll "${WINEPREFIX}/drive_c/windows/system32/" 2>/dev/null || true
fi

# 3. 自动检测并安装 Wine-Mono (.NET CLR 运行时，若未预装)
if [ ! -d "${WINEPREFIX}/drive_c/windows/Microsoft.NET/Framework64/v4.0.30319" ]; then
    MONO_MSI=$(ls /opt/wine-mono*.msi /tmp/wine-mono*.msi /usr/share/wine/mono/wine-mono*.msi /opt/wine-stable/share/wine/mono/wine-mono*.msi 2>/dev/null | head -n 1 || true)
    if [ -n "${MONO_MSI}" ] && [ -f "${MONO_MSI}" ]; then
        echo "[DockerSW] 正在静默安装 Wine-Mono 运行库 (${MONO_MSI})..."
        wine msiexec /i "${MONO_MSI}" /quiet >/dev/null 2>&1 || true
    fi
fi

# 4. 映射 SolidWorks 程序目录
C_SW_CORP="${WINEPREFIX}/drive_c/Program Files/SOLIDWORKS Corp"
C_SW_TARGET="${C_SW_CORP}/SOLIDWORKS"
mkdir -p "${C_SW_CORP}"

if [ -d "${SW_INSTALL_DIR}" ]; then
    echo "[DockerSW] 映射 SolidWorks 目录: ${SW_INSTALL_DIR} -> ${C_SW_TARGET}"
    rm -rf "${C_SW_TARGET}"
    ln -sfn "${SW_INSTALL_DIR}" "${C_SW_TARGET}"

    # 自动注册关键 COM 组件
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
        echo "[DockerSW][WARN] 在 ${SW_INSTALL_DIR} 中未检测到 SLDWORKS.exe"
    fi
else
    echo "[DockerSW][NOTICE] 未挂载外部 SolidWorks 目录 (SW_INSTALL_DIR=${SW_INSTALL_DIR})"
fi

# 自动扫描并导入挂载的 SolidWorks 注册表文件（如 SWHKLM.reg / SWHKCU.reg / sw_com_classes.reg）
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

# 导入镜像内置的 COM 类定义（若存在）
if [ -f "/opt/dockersw/registry/sw_com_classes.reg" ]; then
    wine reg import "/opt/dockersw/registry/sw_com_classes.reg" >/dev/null 2>&1 || true
fi

# 映射 ProgramData（如果提供）
if [ -d "${SW_PROGRAMDATA}" ]; then
    C_PD_TARGET="${WINEPREFIX}/drive_c/ProgramData/SOLIDWORKS"
    mkdir -p "${WINEPREFIX}/drive_c/ProgramData"
    rm -rf "${C_PD_TARGET}"
    ln -sfn "${SW_PROGRAMDATA}" "${C_PD_TARGET}"
    echo "[DockerSW] 映射 ProgramData 目录: ${SW_PROGRAMDATA} -> ${C_PD_TARGET}"
fi

# 3. 许可服务器配置与管理
if [ -n "${SW_LICENSE_SERVER}" ]; then
    echo "[DockerSW] 配置远程许可服务器: ${SW_LICENSE_SERVER}"
    wine reg add 'HKLM\SOFTWARE\FLEXlm License Manager' /v SW_D_LICENSE_FILE /t REG_SZ /d "${SW_LICENSE_SERVER}" /f >/dev/null 2>&1 || true
    wine reg add 'HKCU\SOFTWARE\FLEXlm License Manager' /v SW_D_LICENSE_FILE /t REG_SZ /d "${SW_LICENSE_SERVER}" /f >/dev/null 2>&1 || true
    wine reg add 'HKLM\System\CurrentControlSet\Control\Session Manager\Environment' /v SOLIDWORKS_LICENSE_FILE /t REG_SZ /d "${SW_LICENSE_SERVER}" /f >/dev/null 2>&1 || true
    wine reg add 'HKLM\System\CurrentControlSet\Control\Session Manager\Environment' /v SW_D_LICENSE_FILE /t REG_SZ /d "${SW_LICENSE_SERVER}" /f >/dev/null 2>&1 || true
elif [ "${START_LOCAL_LICENSE}" = "true" ] || [ -f "${FLEXNET_DIR}/lmgrd.exe" ]; then
    if [ -f "${FLEXNET_DIR}/lmgrd.exe" ]; then
        echo "[DockerSW] 正在启动容器内本地 FlexNet 许可服务守护 (lmgrd.exe)..."
        LIC_FILE="${FLEXNET_DIR}/sw_d_SSQ.lic"
        if [ ! -f "${LIC_FILE}" ]; then
            # 兼容任意 .lic 文件
            LIC_FILE=$(ls "${FLEXNET_DIR}"/*.lic 2>/dev/null | head -n 1 || true)
        fi
        
        if [ -n "${LIC_FILE}" ] && [ -f "${LIC_FILE}" ]; then
            (
                cd "${FLEXNET_DIR}"
                nohup wine "${FLEXNET_DIR}/lmgrd.exe" -c "${LIC_FILE}" -l /tmp/flexnet.log >/dev/null 2>&1 &
            )
            echo "[DockerSW] FlexNet 守护已在后台拉起，日志输出: /tmp/flexnet.log"
        else
            echo "[DockerSW][WARN] 未在 ${FLEXNET_DIR} 找到 .lic 授权文件，跳过启动"
        fi
    fi
fi

# 4. 执行传入的命令或默认进入交互
if [ "${1:-}" = "--init-only" ]; then
    echo "[DockerSW] 无头运行环境就绪 (--init-only)"
    exit 0
fi

if [ "$#" -gt 0 ]; then
    echo "[DockerSW] 执行指令: $@"
    exec "$@"
else
    echo "[DockerSW] 容器就绪。可以通过 'dockersw-export' 命令进行批量文件导出。"
    exec /bin/bash
fi

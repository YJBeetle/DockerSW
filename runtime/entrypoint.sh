#!/usr/bin/env bash
set -euo pipefail

export WINEARCH="win64"
export WINEPREFIX="${WINEPREFIX:-/root/.wine}"
export WINEDEBUG="${WINEDEBUG:--all}"
export DISPLAY="${DISPLAY:-:99}"
export DISPLAY_RESOLUTION="${DISPLAY_RESOLUTION:-1920x1080}"
export VNC_ENABLE="${VNC_ENABLE:-false}"
export VNC_VIEW_ONLY="${VNC_VIEW_ONLY:-true}"
export VNC_PORT="${VNC_PORT:-5900}"
export VNC_LISTEN="${VNC_LISTEN:-0.0.0.0}"
VNC_PASSWORD="${VNC_PASSWORD:-}"

export SW_FLEXNET_DIR="${SW_FLEXNET_DIR:-/opt/SolidWorks_Flexnet_Server}"
export SW_LICENSE_SERVER="${SW_LICENSE_SERVER:-}"

export WINEDLLOVERRIDES="concrt140=n,b;msvcp140=n,b;msvcp140_1=n,b;msvcp140_2=n,b;msvcp140_atomic_wait=n,b;msvcp140_codecvt_ids=n,b;vcruntime140=n,b;vcruntime140_1=n,b;vcomp140=n,b;mfc140u=n,b;d3dcompiler_47=n,b;d3d11=n,b;dxgi=n,b"

is_enabled() {
    case "${1,,}" in
        1|true|yes|on) return 0 ;;
        *) return 1 ;;
    esac
}

is_disabled() {
    case "${1,,}" in
        0|false|no|off) return 0 ;;
        *) return 1 ;;
    esac
}

require_boolean() {
    local name="$1"
    local value="$2"
    if ! is_enabled "${value}" && ! is_disabled "${value}"; then
        echo "[DockerSW][ERROR] ${name} 必须是 true/false、1/0、yes/no 或 on/off，当前值: ${value}" >&2
        exit 1
    fi
}

echo "========================================================="
echo "  DockerSW Headless Container (Wine SolidWorks Runtime)  "
echo "========================================================="

# 0. 自动应用/校验 Wine 11.x OpenGL 24-bit DIB 离屏渲染补丁与 Wine-Mono CCW release assertion 补丁
if [ -f "/usr/local/lib/sw-runtime/patch_win32u.pl" ]; then
    perl /usr/local/lib/sw-runtime/patch_win32u.pl >/dev/null 2>&1 || true
fi
if [ -f "/usr/local/lib/sw-runtime/patch_wine_mono.pl" ]; then
    perl /usr/local/lib/sw-runtime/patch_wine_mono.pl >/dev/null 2>&1 || true
fi

# 1. 守护启动 Xvfb 无头虚拟显示服务（COM 消息循环与 3D 渲染必需）
SCREEN_NUM=$(echo "${DISPLAY}" | sed -E 's/.*:([0-9]+).*/\1/')
if [ ! -S "/tmp/.X11-unix/X${SCREEN_NUM}" ]; then
    echo "[DockerSW] 正在拉起 Xvfb 虚拟屏幕 (:${SCREEN_NUM}, ${DISPLAY_RESOLUTION} 24bpp)..."
    Xvfb ":${SCREEN_NUM}" -screen 0 "${DISPLAY_RESOLUTION}x24" -ac +extension GLX +render -noreset >/dev/null 2>&1 &
    XVFB_PID=$!
    for _ in {1..20}; do
        if [ -S "/tmp/.X11-unix/X${SCREEN_NUM}" ]; then
            break
        fi
        sleep 0.2
    done
    echo "[DockerSW] Xvfb 虚拟屏幕 (:${SCREEN_NUM}) 已就绪 (PID: ${XVFB_PID})"
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

# 4. 验证 SolidWorks 主程序目录
C_SW_TARGET="${WINEPREFIX}/drive_c/Program Files/SOLIDWORKS"
if [ -f "${C_SW_TARGET}/SLDWORKS.exe" ]; then
    echo "[DockerSW] 验证主程序: SLDWORKS.exe 存在"
else
    echo "[DockerSW][WARN] 未检测到 SLDWORKS.exe"
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

# 6. 可选的人类 VNC 监看层。它只发布现有 Xvfb 桌面，不参与 SWCLI 或 COM 生命周期。
require_boolean "VNC_ENABLE" "${VNC_ENABLE}"
if is_enabled "${VNC_ENABLE}"; then
    require_boolean "VNC_VIEW_ONLY" "${VNC_VIEW_ONLY}"
    if ! [[ "${VNC_PORT}" =~ ^[0-9]+$ ]] || [ "${VNC_PORT}" -lt 1 ] || [ "${VNC_PORT}" -gt 65535 ]; then
        echo "[DockerSW][ERROR] VNC_PORT 必须是 1-65535 之间的整数，当前值: ${VNC_PORT}" >&2
        exit 1
    fi

    echo "[DockerSW] 正在为 ${DISPLAY} 启动 Openbox 窗口管理器..."
    openbox --sm-disable >/tmp/openbox.log 2>&1 &
    OPENBOX_PID=$!
    sleep 0.2
    if ! kill -0 "${OPENBOX_PID}" 2>/dev/null; then
        echo "[DockerSW][ERROR] Openbox 启动失败，请检查 /tmp/openbox.log" >&2
        exit 1
    fi

    VNC_ARGS=(
        -display "${DISPLAY}"
        -forever
        -shared
        -rfbport "${VNC_PORT}"
        -listen "${VNC_LISTEN}"
        -o /tmp/x11vnc.log
    )
    if is_enabled "${VNC_VIEW_ONLY}"; then
        VNC_ARGS+=(-viewonly)
    fi
    if [ -n "${VNC_PASSWORD}" ]; then
        VNC_PASSWORD_FILE=/tmp/x11vnc.pass
        umask 077
        x11vnc -storepasswd "${VNC_PASSWORD}" "${VNC_PASSWORD_FILE}" >/dev/null
        VNC_ARGS+=(-rfbauth "${VNC_PASSWORD_FILE}")
    else
        VNC_ARGS+=(-nopw)
        echo "[DockerSW][WARN] VNC 未配置密码；请仅将端口发布到可信网络（建议 127.0.0.1）。" >&2
    fi

    echo "[DockerSW] 正在启动 VNC 监看 (${VNC_LISTEN}:${VNC_PORT}, view-only=${VNC_VIEW_ONLY})..."
    x11vnc "${VNC_ARGS[@]}" >/dev/null 2>&1 &
    VNC_PID=$!
    sleep 0.2
    if ! kill -0 "${VNC_PID}" 2>/dev/null; then
        echo "[DockerSW][ERROR] x11vnc 启动失败，请检查 /tmp/x11vnc.log" >&2
        exit 1
    fi
    echo "[DockerSW] VNC 监看已就绪 (PID: ${VNC_PID})"
fi

# 7. 许可服务器配置与管理（运行时）
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
elif [ -f "${SW_FLEXNET_DIR}/lmgrd.exe" ]; then
    echo "[DockerSW] 检测到本地许可服务，正在自动启动 FlexNet 守护 (lmgrd.exe)..."
    LIC_FILE="${SW_FLEXNET_DIR}/sw_d_SSQ.lic"
    if [ ! -f "${LIC_FILE}" ]; then
        LIC_FILE=$(find "${SW_FLEXNET_DIR}" -maxdepth 1 -type f -name '*.lic' -print -quit)
    fi
    [ -n "${LIC_FILE}" ] && [ -f "${LIC_FILE}" ] || {
        echo "[DockerSW][ERROR] 已检测到本地许可服务，但未找到 .lic 文件" >&2
        exit 1
    }

    (
        cd "${SW_FLEXNET_DIR}"
        nohup wine "${SW_FLEXNET_DIR}/lmgrd.exe" -c "${LIC_FILE}" -l /tmp/flexnet.log >/dev/null 2>&1 &
    )

    LOCAL_LICENSE_ADDRESS="25734@127.0.0.1"
    configure_license_server "${LOCAL_LICENSE_ADDRESS}"

    if [ -f "${SW_FLEXNET_DIR}/lmutil.exe" ]; then
        LICENSE_READY=false
        for _ in $(seq 1 30); do
            if timeout --foreground 5 wine "${SW_FLEXNET_DIR}/lmutil.exe" lmstat -a -c "${LOCAL_LICENSE_ADDRESS}" >/dev/null 2>&1; then
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
    echo "[DockerSW][WARN] 未配置 SW_LICENSE_SERVER，且未检测到本地许可服务"
fi

# 8. 执行传入命令或进入交互终端
if [ "$#" -gt 0 ]; then
    echo "[DockerSW] 执行指令: $@"
    exec "$@"
else
    echo "[DockerSW] 容器就绪。使用 'sw-cli' 执行建模、检查与导出。"
    exec /bin/bash
fi

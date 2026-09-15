#!/usr/bin/env bash
set -euo pipefail

export WINEARCH="win64"
export WINEPREFIX="${WINEPREFIX:-/root/.wine}"
export WINEDEBUG="-all"
# prefix 初始化期间禁止 Wine 自动发现/安装 Mono 和 Gecko。Mono 在 wineboot
# 成功后从隔离缓存显式安装，避免自动安装与 msiexec 双重触发。
export WINEDLLOVERRIDES="mscoree,mshtml="

echo "=========================================="
echo "[DockerSW Build] 初始化 WinePrefix 与 Windows Python 环境"
echo "WINEPREFIX: ${WINEPREFIX}"
echo "=========================================="

# 1. 启动临时虚拟屏幕 Xvfb 供构建初始化使用
echo "[INFO] 启动临时 Xvfb 服务 (:99)..."
Xvfb :99 -screen 0 1024x768x24 -ac +extension GLX +render -noreset >/dev/null 2>&1 &
XVFB_PID=$!
trap 'kill ${XVFB_PID} 2>/dev/null || true' EXIT
export DISPLAY=:99
sleep 1

# 2. 初始化 WinePrefix
echo "[INFO] 执行 wineboot 初始化 64 位 Windows 环境..."
timeout --foreground 300 wineboot -u
timeout --foreground 300 wineserver -w
timeout --foreground 60 wine cmd /c ver

# 3. 静默安装 Wine-Mono (.NET CLR 运行时环境)
MONO_INSTALLER=$(find /opt/sw-runtime/cache -maxdepth 1 -type f -name 'wine-mono*.msi' -print -quit 2>/dev/null || true)
if [ -n "${MONO_INSTALLER}" ] && [ -f "${MONO_INSTALLER}" ]; then
    echo "[INFO] 静默安装 Wine-Mono: ${MONO_INSTALLER}..."
    WINEDLLOVERRIDES="mshtml=" timeout --foreground 600 wine msiexec /i "${MONO_INSTALLER}" /quiet /norestart
    timeout --foreground 300 wineserver -w
else
    echo "[ERROR] 未找到隔离缓存中的 Wine-Mono 安装包" >&2
    exit 1
fi

# 后续 Windows 程序使用已经显式安装的 Wine-Mono，仅继续禁用 Gecko。
export WINEDLLOVERRIDES="mshtml="

# 使用与 WineSW 相同、同源构建且经过校验的 x86 stdcall 与托管 COM
# 注册组件。这里只替换 Wine-Mono 组件，不引入任何 macOS Wine 补丁。
echo "[INFO] 配置 Wine-Mono stdcall 与托管 COM 注册运行时..."
/usr/local/lib/sw-runtime/prepare_managed_com.sh

# 4. 导入与商业软件无关的无头运行时配置。SOLIDWORKS 自身的 COM
# 类定义由使用者提供的官方 MSI 注册，公共运行时不预造这些映射。
echo "[INFO] 导入无头运行时注册表配置..."
wine regedit /S /mnt/docker/registry/headless_tweaks.reg
wineserver -w

# 5. 静默安装 64 位 Windows Python 3.11
echo "[INFO] 静默安装 Windows Python 3.11 (TargetDir: C:\\Python311)..."
wine /tmp/python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 TargetDir="C:\\Python311" Include_test=0 Include_doc=0 Include_tcltk=0
wineserver -w

# 6. 安装 pywin32 并执行注册
echo "[INFO] 使用 Windows Python 安装 pywin32..."
wine "C:\\Python311\\python.exe" -m pip install --no-cache-dir --upgrade pip
wine "C:\\Python311\\python.exe" -m pip install --no-cache-dir pywin32
wineserver -w

# 执行 pywin32 注册脚本（若存在）
if [ -f "${WINEPREFIX}/drive_c/Python311/Scripts/pywin32_postinstall.py" ]; then
    wine "C:\\Python311\\python.exe" "C:\\Python311\\Scripts\\pywin32_postinstall.py" -install >/dev/null 2>&1 || true
    wineserver -w
fi

# 7. 反向目录符号链接去重：system32 与 syswow64 100% 保留为真实普通实体目录，
# 补充未拷贝的 Wine 核心工具后，彻底删除 /opt/wine-devel/lib/wine/*-windows 目录并创建指向 system32/syswow64 的目录软链接。
# 消除 540MB 重复物理体积，同时彻底杜绝任何写穿透与 -type f 校验失效问题。
echo "[INFO] 执行 Wine 核心模板目录反向整目录软链接去重..."
if [ -d "/opt/wine-devel/lib/wine/x86_64-windows" ] && [ ! -L "/opt/wine-devel/lib/wine/x86_64-windows" ]; then
    cp -rn /opt/wine-devel/lib/wine/x86_64-windows/* "${WINEPREFIX}/drive_c/windows/system32/" 2>/dev/null || true
    rm -rf /opt/wine-devel/lib/wine/x86_64-windows
    ln -s "${WINEPREFIX}/drive_c/windows/system32" /opt/wine-devel/lib/wine/x86_64-windows
    echo "[INFO] /opt/wine-devel/lib/wine/x86_64-windows -> ${WINEPREFIX}/drive_c/windows/system32 (反向整目录软链接就绪)"
fi

if [ -d "/opt/wine-devel/lib/wine/i386-windows" ] && [ ! -L "/opt/wine-devel/lib/wine/i386-windows" ]; then
    cp -rn /opt/wine-devel/lib/wine/i386-windows/* "${WINEPREFIX}/drive_c/windows/syswow64/" 2>/dev/null || true
    rm -rf /opt/wine-devel/lib/wine/i386-windows
    ln -s "${WINEPREFIX}/drive_c/windows/syswow64" /opt/wine-devel/lib/wine/i386-windows
    echo "[INFO] /opt/wine-devel/lib/wine/i386-windows -> ${WINEPREFIX}/drive_c/windows/syswow64 (反向整目录软链接就绪)"
fi

# 8. 验证环境（确保软链接替换后 Windows 核心与 pywin32 依然完好）
echo "[INFO] 验证 Windows 核心环境与 pywin32 COM 模块..."
wine cmd /c ver
wine "C:\\Python311\\python.exe" -c "import win32com.client, pythoncom; print('[BUILD CHECK OK] Windows pywin32 ready')"
wineserver -w

# 9. 应用 Wine 11.x 24-bit DIB OpenGL 补丁，修复 SolidWorks 3D 着色视图导出四重重复与斜纹网格问题
if [ -f "/usr/local/lib/sw-runtime/patch_win32u.pl" ]; then
    echo "[INFO] 应用 Wine 11.x 24-bit DIB OpenGL 离屏渲染补丁..."
    perl /usr/local/lib/sw-runtime/patch_win32u.pl
fi

echo "[SUCCESS] WinePrefix 与 Windows Python 初始化全部完成！"


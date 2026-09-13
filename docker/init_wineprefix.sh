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
MONO_INSTALLER=$(find /opt/dockersw/cache -maxdepth 1 -type f -name 'wine-mono*.msi' -print -quit 2>/dev/null || true)
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
/usr/local/lib/dockersw/prepare_managed_com.sh

# 4. 导入无头预配注册表与 COM 类定义
echo "[INFO] 导入无头优化注册表与 COM 类映射..."
wine regedit /S /tmp/headless_tweaks.reg
if [ -f "/tmp/sw_com_classes.reg" ]; then
    wine regedit /S /tmp/sw_com_classes.reg
fi
wineserver -w

# 4. 静默安装 64 位 Windows Python 3.11
echo "[INFO] 静默安装 Windows Python 3.11 (TargetDir: C:\\Python311)..."
wine /tmp/python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 TargetDir="C:\\Python311" Include_test=0 Include_doc=0 Include_tcltk=0
wineserver -w

# 5. 安装 pywin32 并执行注册
echo "[INFO] 使用 Windows Python 安装 pywin32..."
wine "C:\\Python311\\python.exe" -m pip install --no-cache-dir --upgrade pip
wine "C:\\Python311\\python.exe" -m pip install --no-cache-dir pywin32
wineserver -w

# 执行 pywin32 注册脚本（若存在）
if [ -f "${WINEPREFIX}/drive_c/Python311/Scripts/pywin32_postinstall.py" ]; then
    wine "C:\\Python311\\python.exe" "C:\\Python311\\Scripts\\pywin32_postinstall.py" -install >/dev/null 2>&1 || true
    wineserver -w
fi

# 6. 验证环境
echo "[INFO] 验证 Windows Python 与 pywin32 COM 模块..."
wine "C:\\Python311\\python.exe" -c "import win32com.client, pythoncom; print('[BUILD CHECK OK] Windows pywin32 ready')"
wineserver -w

echo "[SUCCESS] WinePrefix 与 Windows Python 初始化全部完成！"

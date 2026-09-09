@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo =========================================================
echo    SolidWorks 资产与注册表一键导出工具 (For DockerSW)
echo =========================================================
echo.

:: 检查管理员权限并自动提权
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [提示] 正在请求管理员权限以导出 HKLM 注册表...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

set SCRIPT_DIR=%~dp0
set PS_SCRIPT=%SCRIPT_DIR%collect_sw.ps1

if not exist "%PS_SCRIPT%" (
    echo [错误] 未找到 %PS_SCRIPT% 文件！
    pause
    exit /b 1
)

echo [INFO] 正在执行 PowerShell 收集脚本...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %*

echo.
echo 按任意键退出...
pause >nul

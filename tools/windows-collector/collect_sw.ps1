<#
.SYNOPSIS
    SolidWorks 真机资产与注册表自动抽取工具（专为 DockerSW 定制）
.DESCRIPTION
    自动探测 Windows 系统中已安装的 SolidWorks 2022-2026 程序目录、注册表与 FlexNet 授权文件，
    一键打包抽取为可直接挂载到 DockerSW 容器或用于制作私有镜像的干净目录结构。
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File collect_sw.ps1
    powershell -ExecutionPolicy Bypass -File collect_sw.ps1 -OutputDir "D:\DockerSW_Payload"
#>

[CmdletBinding()]
param (
    [Parameter(Mandatory = $false)]
    [string]$OutputDir = ".\DockerSW_Assets",

    [Parameter(Mandatory = $false)]
    [switch]$SkipBinaryCopy = $false
)

# 确保以管理员权限运行（导出 HKLM 注册表与读取 Program Files 建议提权）
$IsAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $IsAdmin) {
    Write-Warning "【提示】建议右键使用「以管理员身份运行」，以确保完整导出 HKLM 注册表与系统目录权限。"
}

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "   SolidWorks 真机资产抽取与导出工具 (For DockerSW)     " -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan

# 1. 规范化输出路径
$TargetDir = (New-Item -ItemType Directory -Force -Path $OutputDir).FullName
Write-Host "[1/5] 导出目标根目录: $TargetDir" -ForegroundColor Green

# 2. 智能探测 SolidWorks 安装路径
Write-Host "[2/5] 正在搜索已安装的 SolidWorks 主程序..." -ForegroundColor Yellow
$SwInstallPath = $null

# 优先从注册表检索安装路径
$RegPathsToCheck = @(
    "HKLM:\SOFTWARE\SolidWorks\SOLIDWORKS 2026\Setup",
    "HKLM:\SOFTWARE\SolidWorks\SOLIDWORKS 2025\Setup",
    "HKLM:\SOFTWARE\SolidWorks\SOLIDWORKS 2024\Setup",
    "HKLM:\SOFTWARE\SolidWorks\SOLIDWORKS 2023\Setup",
    "HKLM:\SOFTWARE\SolidWorks\SOLIDWORKS 2022\Setup",
    "HKLM:\SOFTWARE\SolidWorks\Setup"
)

foreach ($reg in $RegPathsToCheck) {
    if (Test-Path $reg) {
        $val = (Get-ItemProperty -Path $reg -ErrorAction SilentlyContinue)."SolidWorks Folder"
        if ($val -and (Test-Path (Join-Path $val "SLDWORKS.exe"))) {
            $SwInstallPath = $val
            break
        }
    }
}

# 若注册表未查到，遍历所有本地磁盘常见路径
if (-not $SwInstallPath) {
    $Drives = Get-PSDrive -PSProvider FileSystem | Select-Object -ExpandProperty Root
    foreach ($drive in $Drives) {
        $candidate = Join-Path $drive "Program Files\SOLIDWORKS Corp\SOLIDWORKS"
        if (Test-Path (Join-Path $candidate "SLDWORKS.exe")) {
            $SwInstallPath = $candidate
            break
        }
    }
}

if ($SwInstallPath -and (Test-Path (Join-Path $SwInstallPath "SLDWORKS.exe"))) {
    Write-Host "  -> 成功定位 SolidWorks 主程序目录: $SwInstallPath" -ForegroundColor Green
} else {
    Write-Host "  -> 未能自动定位 SLDWORKS.exe，请输入完整路径（例如 C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS）:" -ForegroundColor Magenta
    $UserInput = Read-Host "SolidWorks 路径"
    if ($UserInput -and (Test-Path (Join-Path $UserInput "SLDWORKS.exe"))) {
        $SwInstallPath = $UserInput
    } else {
        Write-Error "路径无效或未找到 SLDWORKS.exe，脚本终止。"
        exit 1
    }
}

# 3. 智能探测 FlexNet 许可服务器目录
Write-Host "[3/5] 正在检索 FlexNet 授权服务器..." -ForegroundColor Yellow
$FlexnetPath = $null
$FlexCandidates = @(
    "C:\SolidWorks_Flexnet_Server",
    "C:\opt\SolidWorks_Flexnet_Server",
    "D:\SolidWorks_Flexnet_Server",
    "D:\opt\SolidWorks_Flexnet_Server"
)
foreach ($fc in $FlexCandidates) {
    if (Test-Path (Join-Path $fc "lmgrd.exe")) {
        $FlexnetPath = $fc
        break
    }
}
if ($FlexnetPath) {
    Write-Host "  -> 找到本地 FlexNet 授权服务目录: $FlexnetPath" -ForegroundColor Green
} else {
    Write-Host "  -> 未检测到本地 FlexNet 服务目录（若使用公司远程浮动授权可忽略此项）。" -ForegroundColor DarkGray
}

# 4. 导出核心注册表文件
Write-Host "[4/5] 正在导出注册表 (SWHKLM.reg & SWHKCU.reg)..." -ForegroundColor Yellow

$HklmFile = Join-Path $TargetDir "SWHKLM.reg"
$HkcuFile = Join-Path $TargetDir "SWHKCU.reg"

# 导出 HKLM 注册表
& reg.exe export "HKLM\SOFTWARE\SolidWorks" "$HklmFile" /y | Out-Null
if ($LASTEXITCODE -eq 0 -and (Test-Path $HklmFile)) {
    Write-Host "  -> [OK] 已导出: SWHKLM.reg" -ForegroundColor Green
} else {
    Write-Warning "  -> [WARN] 导出 HKLM\SOFTWARE\SolidWorks 失败或该键不存在。"
}

# 导出 HKCU 注册表
& reg.exe export "HKCU\Software\SolidWorks" "$HkcuFile" /y | Out-Null
if ($LASTEXITCODE -eq 0 -and (Test-Path $HkcuFile)) {
    Write-Host "  -> [OK] 已导出: SWHKCU.reg" -ForegroundColor Green
} else {
    Write-Warning "  -> [WARN] 导出 HKCU\Software\SolidWorks 失败。"
}

# 附加导出 COM 接口 CLSID（确保 Wine 下能无损通过 DispatchEx 识别 ProgID）
$ComFile = Join-Path $TargetDir "SW_COM_CLASSES.reg"
& reg.exe export "HKCR\SldWorks.Application" "$ComFile" /y | Out-Null 2>&1
if (Test-Path $ComFile) {
    Write-Host "  -> [OK] 已导出: SW_COM_CLASSES.reg" -ForegroundColor Green
}

# 5. 复制 SolidWorks 主程序目录与相关资产
Write-Host "[5/5] 正在收集复制文件资产（使用高效多线程 robocopy）..." -ForegroundColor Yellow

if ($SkipBinaryCopy) {
    Write-Host "  -> 用户指定跳过二进制文件拷贝。" -ForegroundColor DarkGray
} else {
    # 5.1 复制 SOLIDWORKS 主程序目录
    $DestSw = Join-Path $TargetDir "SOLIDWORKS"
    Write-Host "  -> 复制 SolidWorks 核心程序到: $DestSw ..." -ForegroundColor Cyan
    # 使用 robocopy 多线程镜像复制，排除无用的临时缓存文件
    & robocopy "$SwInstallPath" "$DestSw" /E /MT:8 /R:1 /W:1 /XF *.tmp *.log /NDL /NFL /NP
    Write-Host "  -> [OK] SolidWorks 主程序拷贝完成！" -ForegroundColor Green

    # 5.2 复制 FlexNet 服务目录（若存在）
    if ($FlexnetPath) {
        $DestFlex = Join-Path $TargetDir "SolidWorks_Flexnet_Server"
        Write-Host "  -> 复制 FlexNet 授权目录到: $DestFlex ..." -ForegroundColor Cyan
        & robocopy "$FlexnetPath" "$DestFlex" /E /MT:8 /R:1 /W:1 /NDL /NFL /NP
        Write-Host "  -> [OK] FlexNet 授权服务目录拷贝完成！" -ForegroundColor Green
    }

    # 5.3 复制 ProgramData\SOLIDWORKS（若存在）
    $ProgramDataSw = "C:\ProgramData\SOLIDWORKS"
    if (Test-Path $ProgramDataSw) {
        $DestPd = Join-Path $TargetDir "ProgramData\SOLIDWORKS"
        Write-Host "  -> 复制 ProgramData 模板数据到: $DestPd ..." -ForegroundColor Cyan
        & robocopy "$ProgramDataSw" "$DestPd" /E /MT:8 /R:1 /W:1 /NDL /NFL /NP
        Write-Host "  -> [OK] ProgramData 模板数据拷贝完成！" -ForegroundColor Green
    }
}

Write-Host "`n=========================================================" -ForegroundColor Green
Write-Host " [SUCCESS] 资产收集已全部完成！" -ForegroundColor Green
Write-Host " 输出目录内容清单:" -ForegroundColor Green
Get-ChildItem -Path $TargetDir | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
Write-Host " 这些文件可以直接提供给 DockerSW 容器挂载，或用于下游私有镜像构建！" -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Green

# DockerSW: 无头 SolidWorks Linux 容器化与 CI 自动化导出环境

[![Build and Test DockerSW](https://github.com/YJBeetle/DockerSW/actions/workflows/docker-build.yml/badge.svg)](https://github.com/YJBeetle/DockerSW/actions/workflows/docker-build.yml)
[![Docker Image](https://img.shields.io/badge/ghcr.io-sw--runtime-blue?logo=docker)](https://github.com/YJBeetle/DockerSW/pkgs/container/sw-runtime)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**DockerSW** 专为在 **Linux Docker 容器**（如 GitLab CI Runner、Kubernetes 集群、Linux 物理机）中通过 **Wine** 无头（Headless）静默运行 SolidWorks 并进行 CAD 资产批量自动化导出而设计。

---

## 🌟 核心特性

- 📦 **版权完全隔离与两阶段构建**：公开仓库**不包含任何 SolidWorks 商业专有二进制或授权文件**，仅构建通用运行时（Ubuntu + Wine 11.16 + Wine-Mono 11.3.0 + Xvfb + Windows Python 3.11 + pywin32）。
- 🧩 **真实 Login Manager/COM 安装链**：运行时内置与 WineSW 相同的 x86 stdcall、`RegistrationServices`、x86/x64 托管 RegAsm 与 `stdole` 修复；`dockersw-install` 会在主 MSI 前安装介质中的官方 Login Manager，并校验真实 CLSID、`mscoree.dll`、托管类与 CodeBase。
- 🚀 **开箱即用的导出引擎 (`dockersw-export`)**：
  - 零件与装配体 (`.SLDPRT` / `.SLDASM`) ➡️ 导出为 `.STEP`；
  - 工程图 (`.SLDDRW`) ➡️ 同步导出为 `.PDF` 与 `.DWG`；
  - 渲染模型 (`*.REND.SLDASM`) ➡️ 导出为 `.GLB`；
  - 自动识别 Linux / Wine Windows 绝对与相对路径，清单无需反斜杠改造。
- 🛡️ **CI 静默保障与异常兜底**：
  - 安装所需的 Login Manager 与托管 COM，不把缺少组件导致的致命弹窗误判为可忽略提示；
  - 底层注册表关闭登录入口（`EnableSldLoginManager=0`）与崩溃调试器（`AeDebug=0`）；
  - 核心 API 采用 `OpenDoc6(swOpenDocOptions_Silent)` 与 `SaveAs3(swSaveAsOptions_Silent)`；
  - 单个文件失败不中断批处理，最终统计并输出清晰的 Exit Code（全部成功返回 0，失败返回 1）。
- 🔌 **智能许可管理**：支持内网浮动授权（`SW_LICENSE_SERVER`）与本地授权守护自启（`START_LOCAL_LICENSE`）双模式。

---

## 🏗️ 架构概览

```
               [ GitHub Actions 构建发布 ]
                             │
                             ▼
         [ 公开基础镜像: ghcr.io/yjbeetle/sw-runtime:latest ]
         ┌──────────────────────────────────────────────┐
         │ Ubuntu 22.04 LTS x86_64                      │
         │  ├─ Xvfb (:99 无头虚拟屏幕, 保障 COM 消息泵) │
         │  ├─ Wine 11.16 + Wine-Mono 11.3.0           │
         │  ├─ stdcall 与托管 COM 注册修复              │
         │  ├─ Windows Python 3.11 + pywin32            │
         │  ├─ 无头优化注册表 (跳过登录/EULA/崩溃弹窗)   │
         │  └─ dockersw-export 命令行批处理工具         │
         └──────────────────────┬───────────────────────┘
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼ 运行方式 A: Volume 挂载 (推荐用于 CI)           ▼ 运行方式 B: 企业私有镜像
┌────────────────────────────────┐              ┌────────────────────────────────┐
│ GitLab CI Runner / Docker      │              │ 企业私有 Docker 镜像           │
│ docker run -v /data/SW:/opt/sw │              │ FROM ghcr.io/.../sw-runtime     │
│  -e SW_LICENSE_SERVER=...      │              │ COPY ./sw /opt/solidworks      │
│  ghcr.io/yjbeetle/sw-runtime   │              │ ENV START_LOCAL_LICENSE=true   │
└────────────────────────────────┘              └────────────────────────────────┘
```

---

## ⚙️ 环境变量与配置参数

| 环境变量 | 默认值 | 作用说明 |
|---|---|---|
| `SW_INSTALL_DIR` | `/opt/solidworks` | SolidWorks 根目录（包含 `SLDWORKS.exe`），容器启动时自动软链接至 Wine 虚拟 C 盘并注册 COM |
| `SW_LICENSE_SERVER` | *(空)* | 远程 FlexNet 许可服务器地址（例如 `25734@192.168.1.100`），若配置则优先使用 |
| `START_LOCAL_LICENSE`| `false` | 设为 `true` 时，若未提供远程许可且存在本地服务目录，容器启动时自动后台运行 `lmgrd.exe` |
| `FLEXNET_DIR` | `/opt/SolidWorks_Flexnet_Server` | 本地 FlexNet 许可守护程序目录（包含 `lmgrd.exe` 与授权文件） |
| `DISPLAY` | `:99` | 虚拟屏幕 DISPLAY，由容器内后台守护的 `Xvfb` 托管 |

---

## 🚀 快速上手与使用示例

### 0. 从合法取得的官方完整介质静默安装

`dockersw-install` 接受已解压目录、ISO 或受支持的归档。介质必须同时包含主 MSI、VC++ 运行库以及 `swloginmgr/SOLIDWORKS Login Manager.msi`：

```bash
dockersw-install --media /private-media/SOLIDWORKS.iso
```

脚本会依次准备固定版本的 Wine-Mono COM 运行时、安装 VC++、静默安装 Login Manager、验证其真实 COM 注册，再执行 SOLIDWORKS 主 MSI。安装日志可能包含序列号属性，默认仅保存在权限受限的 `/var/log/dockersw-install`。公开镜像不下载、不内置 SOLIDWORKS 安装介质或授权内容。

### 1. 本地 / 服务器 Docker Compose 挂载调试

如果宿主机或网络存储上已有一份 SolidWorks 安装目录（例如由 WineSW 初始化生成的 `C` 盘目录），可直接使用 `examples/docker-compose.yml` 进行调试：

```bash
# 进入项目目录，指定 SW 实体目录启动（支持缺省回退）
SW_DIR="/path/to/SOLIDWORKS" docker compose -f examples/docker-compose.yml up
```

`examples/docker-compose.yml` 关键配置示范：
```yaml
services:
  dockersw-exporter:
    image: ghcr.io/yjbeetle/sw-runtime:latest
    environment:
      - START_LOCAL_LICENSE=true
    volumes:
      - /path/to/SOLIDWORKS:/opt/solidworks:ro
      - /path/to/SolidWorks_Flexnet_Server:/opt/SolidWorks_Flexnet_Server:ro
      - ./:/workspace
    working_dir: /workspace
    command: >
      dockersw-export
      --list /workspace/examples/export-list-demo.txt
      --workspace /workspace
      --outdir /workspace/dist_output
```

---

### 2. GitLab CI 流水线集成

在 GitLab 项目的 `.gitlab-ci.yml` 中集成无头自动导出（完整示范见 [examples/gitlab-ci/.gitlab-ci.yml](examples/gitlab-ci/.gitlab-ci.yml)）：

```yaml
export_cad_assets:
  stage: build
  image: ghcr.io/yjbeetle/sw-runtime:latest
  variables:
    # 指定公司内部的浮动许可服务器
    SW_LICENSE_SERVER: "25734@192.168.1.100"
  script:
    - mkdir -p ./dist
    - >
      dockersw-export
      --list ./export_list.txt
      --workspace "$CI_PROJECT_DIR"
      --outdir ./dist
  artifacts:
    name: "CAD_Export_${CI_COMMIT_SHORT_SHA}"
    paths:
      - ./dist/
```

> **提示**：若使用基于 Docker 的 GitLab Runner，只需在 Runner 宿主机的 `/etc/gitlab-runner/config.toml` 中的 `volumes` 字段加上 SolidWorks 缓存路径即可：
> ```toml
> volumes = ["/data/solidworks:/opt/solidworks:ro", "/cache"]
> ```

---

### 3. 构建企业私有定制镜像（零挂载依赖）

在企业内部的私有 Git 仓库中，仅需编写如下 5 行 `Dockerfile`（参考 [examples/private-image/Dockerfile](examples/private-image/Dockerfile)）：

```dockerfile
FROM ghcr.io/yjbeetle/sw-runtime:latest

# 装配内部保存的 SolidWorks 程序与授权
COPY ./SOLIDWORKS /opt/solidworks
COPY ./SolidWorks_Flexnet_Server /opt/SolidWorks_Flexnet_Server

# 激活自动拉起授权服务开关
ENV START_LOCAL_LICENSE=true
```

编译并推送到内部私有镜像仓库后，任意机器拉取即可开箱即用，无需配置额外挂载！

---

### 4. 导出清单格式范例 (`export_list.txt`)

清单文本支持标准相对路径、UTF-8 编码、行内注释（`#`）及空行（参考 [examples/export-list-demo.txt](examples/export-list-demo.txt)）：

```text
# 装配体工程图（自动输出 .PDF 与 .DWG）
COT[N]/Main/N_MainAssembly.SLDDRW

# 关键零件（自动输出 .STEP）与零件工程图
COT[N]/Main/N_Antenna.SLDPRT
COT[N]/Main/N_Antenna.SLDDRW
COT[N]/Main/N_Casing.SLDPRT
COT[N]/Main/N_Casing.SLDDRW

# 专用渲染装配体（自动输出 .GLB）
Render/Main_Assembly.REND.SLDASM
```

---

### 5. 在 Windows 真机上一键获取 SolidWorks 资产与注册表

本项目在 `tools/windows-collector/` 下提供了 Windows 真机一键资产抽取工具：
* [`collect_sw.bat`](tools/windows-collector/collect_sw.bat)：双击即自动以管理员权限调用抽取脚本；
* [`collect_sw.ps1`](tools/windows-collector/collect_sw.ps1)：基于 PowerShell 的全自动智能探测与收集器。

**功能与效果：**
1. 自动从注册表和磁盘探测已安装的 SolidWorks 主程序目录（`SLDWORKS.exe`）；
2. 自动导出干净无损的核心注册表：`SWHKLM.reg`、`SWHKCU.reg` 与 COM 接口注册表 `SW_COM_CLASSES.reg`；
3. 自动探测并打包本地 FlexNet 授权服务器（若存在）；
4. 通过高性能多线程 `robocopy` 镜像复制程序与数据文件，排除临时缓存。

**在 Windows 上的运行方式：**
在安装了 SolidWorks 的 Windows 机器上，右键点击 `collect_sw.bat` 选择 **「以管理员身份运行」**，脚本将自动在当前目录下生成可以直接挂载给 DockerSW 使用的 `DockerSW_Assets/` 资产包：
```
DockerSW_Assets/
├── SOLIDWORKS/                  # 主程序目录
├── SolidWorks_Flexnet_Server/   # 授权服务（若存在）
├── ProgramData/                 # 配置与模板（若存在）
├── SWHKLM.reg                   # 机器注册表
└── SWHKCU.reg                   # 用户注册表
```

---

## 🧪 本地测试与自检

本项目包含了对路径转换与导出规则推导的独立单元测试：

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

CI 构建期间，GitHub Actions 还会拉起真实容器，校验 Wine 11.16、Wine-Mono 11.3.0 的 stdcall/托管 COM 注册组件，以及 Windows Python `win32com` 模块。SOLIDWORKS 与 Login Manager 的实际安装测试由持有合法介质的私有下游流水线完成。

---

## 📄 版权与免责声明

1. 本项目仅包含 Wine 环境与自动化导出脚本，不提供任何 SOLIDWORKS® 商业软件的二进制程序或破解授权。
2. SOLIDWORKS® 为达索系统（Dassault Systèmes）的注册商标。请在拥有正版商业授权的前提下使用自动化集成功能。

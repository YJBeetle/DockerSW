# DockerSW：SOLIDWORKS Wine 运行时、静默安装与自动化导出

[![Build and Test DockerSW](https://github.com/YJBeetle/DockerSW/actions/workflows/docker-build.yml/badge.svg)](https://github.com/YJBeetle/DockerSW/actions/workflows/docker-build.yml)
[![Docker Image](https://img.shields.io/badge/ghcr.io-sw--runtime-blue?logo=docker)](https://github.com/YJBeetle/DockerSW/pkgs/container/sw-runtime)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

DockerSW 为 Linux 容器提供经过固定版本验证的 Wine、Wine-Mono、托管 COM、Windows Python 及无头显示环境，并内置：

- `sw-install`：从用户提供的完整 SOLIDWORKS 安装介质执行静默安装；
- `sw-export`：通过 SOLIDWORKS COM API 批量导出 CAD 文件。

> [!IMPORTANT]
> 公开镜像 `ghcr.io/yjbeetle/sw-runtime` **不包含** SOLIDWORKS 安装介质、程序文件、序列号、许可文件或许可服务器。使用者必须自行合法取得安装介质，并在自己的私有环境中构建预安装镜像或持久化安装结果。

## 核心能力

- **可复现的公开运行时**：Ubuntu 22.04、Wine 11.16、Wine-Mono 11.3.0、Xvfb、Windows Python 3.11 与 pywin32。
- **完整安装链**：检查介质布局，安装 VC++ 运行库与官方 Login Manager，再执行 SOLIDWORKS 主 MSI。
- **Wine COM 兼容修复**：包含与 WineSW 对齐的 x86 stdcall、`RegistrationServices`、x86/x64 托管 RegAsm 与 `stdole` 修复，并验证 Login Manager 的真实 COM 注册。
- **显式 EULA 处理**：仅在调用者传入 `--accept-eula` 后，才根据 MSI 版本写入对应的接受标记；公共运行时不预置接受状态。
- **无头批量导出**：
  - `.SLDPRT` / `.SLDASM` 导出为 `.STEP`；
  - `.SLDDRW` 导出为 `.PDF` 与 `.DWG`；
  - `*.REND.SLDASM` 导出为 `.GLB`；
  - 支持 Linux、Wine Windows、绝对及相对路径。
- **两种许可接入方式**：优先使用局域网浮动许可服务器，也可按需挂载 `lmgrd.exe` 与许可文件并在容器内启动。

## 推荐架构

```text
合法取得的完整安装介质
          │
          │ sw-install --accept-eula
          ▼
ghcr.io/yjbeetle/sw-runtime
  Wine / Mono / COM / 安装与导出工具
          │
          │ 在可信私有 CI 中构建
          ▼
私有 sw-preinstalled 镜像
          │
          ├── SW_LICENSE_SERVER → 使用者局域网许可服务器（推荐）
          └── 挂载 lmgrd + START_LOCAL_LICENSE=true（可选）
          │
          ▼
       sw-export
```

公开 CI 只构建和测试通用 `sw-runtime`。SOLIDWORKS 的下载、安装、许可配置和最终 `sw-preinstalled` 镜像都应留在使用者自己的私有基础设施中。

## 安装 SOLIDWORKS

### 1. 校验安装介质

`sw-install` 接受已解压目录、ISO 或受支持的归档。完整介质至少需要包含主 MSI、VC++ x64 运行库、.NET 4.8 安装包及 `swloginmgr/SOLIDWORKS Login Manager.msi`。

可以先只校验介质，不启动 Wine 或安装任何组件：

```bash
docker run --rm \
  -v /path/to/private-media:/private-media:ro \
  ghcr.io/yjbeetle/sw-runtime:latest \
  sw-install --media /private-media/SOLIDWORKS.iso --validate-only
```

### 2. 显式接受 EULA 并安装

无人值守安装时，需要由实际安装者明确作出接受决定：

```bash
sw-install \
  --media /private-media/SOLIDWORKS.iso \
  --accept-eula
```

`--accept-eula` 的语义如下：

- 传入该参数即表示调用者确认自己或所属组织已经阅读并接受该安装介质所适用的 SOLIDWORKS 最终用户许可协议；
- 脚本会读取主 MSI 的 `ProductVersion`，推导产品年份与 Service Pack，并在当前 Wine 用户注册表中写入对应的 EULA 接受标记；
- 未传入该参数时，脚本不会写入任何 EULA 接受标记，介质自身仍可能要求交互确认或拒绝继续安装；
- 该参数不会下载软件、授予许可证、配置序列号，也不能替代调用者审阅和遵守实际协议；
- 出于需要显式确认的考虑，`--accept-eula` **没有环境变量等价项**。

脚本随后会准备固定版本的 Wine-Mono COM 环境，安装 VC++ 与官方 Login Manager，验证真实 COM 注册，执行主 MSI，并确认 `SLDWORKS.exe` 已产生。安装日志默认写入权限受限的 `/var/log/sw-install`；日志可能包含 MSI 属性或序列号，应仅保存在可信私有环境。

> [!NOTE]
> 直接在一次性 `docker run --rm` 容器中安装不会保留结果。生产使用应在私有 Dockerfile 中执行安装，或将整个 `WINEPREFIX` 持久化。

### 3. 构建私有预安装镜像

[examples/private-image/Dockerfile](examples/private-image/Dockerfile) 使用 BuildKit 临时挂载安装介质，安装结束后介质不会被 `COPY` 到最终层：

```bash
docker build \
  -f examples/private-image/Dockerfile \
  -t registry.internal.mycompany.com/cad/sw-preinstalled:latest \
  .
```

示例预期介质位于构建上下文的 `private-media/SOLIDWORKS.iso`。不要把介质、序列号属性文件、许可文件或生成的安装日志提交到公开仓库。即使使用 BuildKit 临时挂载，也应只在可信私有 Builder 上构建，并按组织策略保护或清理构建缓存。

如需传入序列号或站点专用 MSI 属性，优先使用 `SW_MSI_PROPERTIES_FILE` 指向私有 CI Secret 文件，不要通过 Dockerfile 的 `ARG`、`ENV` 或公开构建日志传递。

## `sw-install` 参数与环境变量

| 命令行参数 | 环境变量 | 默认值 | 说明 |
|---|---|---|---|
| `--media PATH` | `SW_MEDIA_PATH` | 无 | 完整安装介质目录、ISO 或归档；必填 |
| `--registry-dir PATH` | `SW_INSTALL_REGISTRY_DIR` | 空 | 主 MSI 前导入目录内的私有 `.reg` 文件 |
| `--msi PATH` | `SW_MSI_RELATIVE_PATH` | `swwi/data/solidworks.msi` | 相对于介质根目录的主 MSI 路径 |
| `--property NAME=VALUE` | `SW_MSI_PROPERTIES_FILE` | 空 | 追加 MSI 属性；文件格式为每行一个 `NAME=VALUE` |
| `--log-dir PATH` | `SW_INSTALL_LOG_DIR` | `/var/log/sw-install` | 权限受限的安装日志目录 |
| `--timeout SECONDS` | `SW_INSTALL_TIMEOUT` | `10800` | 每个长时间安装步骤的超时秒数 |
| `--accept-eula` | 无 | 关闭 | 显式确认接受适用 EULA，并写入由介质版本推导的标记 |
| `--validate-only` | 无 | 关闭 | 只提取并校验介质，不运行 Wine |
| 无 | `SW_INSTALL_WPF_THEMES` | `true` | 是否从官方 .NET 4.8 包提取所需 WPF 主题组件 |
| 无 | `WINEPREFIX` | `/root/.wine` | 安装结果所在的 Wine 前缀 |

运行 `sw-install --help` 可查看当前命令行说明。

## 运行私有预安装镜像

### Docker Compose

[examples/docker-compose.yml](examples/docker-compose.yml) 只接受已安装好 SOLIDWORKS 的私有镜像：

```bash
SW_IMAGE=registry.internal.mycompany.com/cad/sw-preinstalled:latest \
SW_LICENSE_SERVER=25734@192.168.1.100 \
CAD_WORKSPACE=/path/to/cad-project \
EXPORT_OUTPUT=/path/to/dist \
docker compose -f examples/docker-compose.yml up --abort-on-container-exit
```

远程许可服务器是推荐模式。若使用者确实需要在容器内启动自己的许可服务，可把包含 `lmgrd.exe` 和 `.lic` 的目录挂载至 `/opt/SolidWorks_Flexnet_Server`，并设置 `START_LOCAL_LICENSE=true`。公开镜像不提供这些文件。

### GitLab CI

在 GitLab 中使用私有 `sw-preinstalled` 镜像执行导出；完整示例见 [examples/gitlab-ci/.gitlab-ci.yml](examples/gitlab-ci/.gitlab-ci.yml)：

```yaml
export_cad_assets:
  stage: export
  image: registry.internal.mycompany.com/cad/sw-preinstalled:latest
  script:
    - mkdir -p ./dist
    - >
      sw-export
      --list ./export_list.txt
      --workspace "$CI_PROJECT_DIR"
      --outdir ./dist
  artifacts:
    paths:
      - ./dist/
```

将 `SW_LICENSE_SERVER` 配置为 GitLab 项目的 masked/protected CI/CD Variable，不要把实际内网地址、序列号或许可内容写入仓库。公开 `sw-runtime` 本身没有 SOLIDWORKS，不能直接执行真实 CAD 导出。

## 运行时环境变量

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `SW_INSTALL_DIR` | `/opt/solidworks` | 可选的外部 SOLIDWORKS 程序目录；完整 MSI 安装通常位于 `WINEPREFIX` 内 |
| `SW_PROGRAMDATA` | `/opt/solidworks_programdata` | 可选的外部 ProgramData 映射目录 |
| `SW_LICENSE_SERVER` | 空 | 远程 FlexNet 服务器，例如 `25734@192.168.1.100`；配置后优先使用 |
| `START_LOCAL_LICENSE` | `false` | 设为 `true` 时启动已挂载的本地 `lmgrd.exe` |
| `FLEXNET_DIR` | `/opt/SolidWorks_Flexnet_Server` | 本地 FlexNet 目录，需由使用者提供 `lmgrd.exe` 与 `.lic` |
| `DISPLAY` | `:99` | 由容器内 Xvfb 托管的虚拟屏幕 |
| `WINEPREFIX` | `/root/.wine` | Wine 前缀路径 |

## 导出清单

清单支持 UTF-8、相对或绝对路径、空行及以 `#` 开头的注释。示例见 [examples/export-list-demo.txt](examples/export-list-demo.txt)：

```text
# 装配体工程图：输出 PDF 与 DWG
SampleProject/Drawings/MainAssembly.SLDDRW

# 零件：输出 STEP
SampleProject/Parts/MountingBracket.SLDPRT

# 渲染装配体：输出 GLB
SampleProject/Render/MainAssembly.REND.SLDASM
```

## 测试

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

GitHub Actions 会构建真实容器，并校验固定 Wine/Wine-Mono 版本、stdcall 与托管 COM 修复、Windows Python/pywin32、`sw-install` 和 `sw-export`。SOLIDWORKS 与 Login Manager 的实际安装测试需要商业介质，因此应由持有合法介质的私有下游 CI 完成。

当前安装链主要按 SOLIDWORKS 2025 SP5.0 介质验证；其他版本的介质布局、安装属性或 Wine 行为可能不同，不能视为已经兼容。

## 许可与免责声明

1. 本项目是非官方兼容与自动化工具，与 Dassault Systèmes 或 SOLIDWORKS 无隶属、认可或支持关系；Wine 运行方式也不属于厂商官方支持的平台。
2. 本项目只提供通用 Wine 运行时、安装辅助与导出脚本，不分发 SOLIDWORKS 商业软件、安装介质、序列号、许可文件或破解授权。
3. 使用者应自行确认其下载、安装、容器化、缓存、内部再分发和自动化使用方式符合适用的许可协议、合同与当地法律。
4. SOLIDWORKS 是 Dassault Systèmes 的注册商标。

# DockerSW：SOLIDWORKS Wine 运行时、静默安装与自动化导出

[![Build & Verify](https://github.com/YJBeetle/DockerSW/actions/workflows/build.yml/badge.svg)](https://github.com/YJBeetle/DockerSW/actions/workflows/build.yml)
[![Docker Image](https://img.shields.io/badge/ghcr.io-sw--runtime-blue?logo=docker)](https://github.com/YJBeetle/DockerSW/pkgs/container/sw-runtime)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

DockerSW 为 Linux 容器提供经过固定版本验证的 Wine、Wine-Mono、托管 COM、Windows Python 及无头显示环境，并提供：

- `sw-install`：从用户提供的完整 SOLIDWORKS 安装介质执行静默安装；
- [SWCLI](https://github.com/YJBeetle/SWCLI)：面向 AI 与自动化的 typed SOLIDWORKS 命令行及常驻 daemon 服务。

> [!IMPORTANT]
> 公开镜像 `ghcr.io/yjbeetle/sw-runtime` **不包含** SOLIDWORKS 安装介质、程序文件、序列号、许可文件或许可服务器。使用者必须自行合法取得安装介质，并在自己的私有环境中构建预安装镜像或持久化安装结果。

## 核心能力

- **可复现的公开运行时**：Ubuntu 22.04、Wine 11.16、Wine-Mono 11.3.0、Xvfb、Windows Python 3.11 与 pywin32。
- **完整安装链**：检查介质布局，安装 VC++ 运行库与官方 Login Manager，再执行 SOLIDWORKS 主 MSI，并验证 MSI 产生的主程序 COM 注册。
- **Wine COM 兼容修复**：包含与 MacSW 对齐的 x86 stdcall、`RegistrationServices`、x86/x64 托管 RegAsm 与 `stdole` 修复，并验证 Login Manager 的真实托管 COM 注册。
- **显式 EULA 处理**：仅在调用者传入 `--accept-eula` 后，才根据 MSI 版本写入对应的接受标记；公共运行时不预置接受状态。
- **无头自动化导出**：
  - `.SLDPRT` / `.SLDASM` 导出为 `.STEP`；
  - `.SLDDRW` 导出为 `.PDF` 与 `.DWG`；
  - `*.REND.SLDASM` 导出为 `.GLB`；
  - 支持 Linux、Wine Windows、绝对及相对路径。
- **两种许可接入方式**：优先使用局域网浮动许可服务器，也可按需挂载 `lmgrd.exe` 与许可文件并在容器内启动。
- **固定 SWCLI 版本**：DockerSW 以 Git submodule 固定经过真实 Wine/SOLIDWORKS 冒烟验证的 SWCLI 提交，并将其装入对应的 `-cli` 镜像；容器只负责路径、进程、许可与显示环境适配。

## 默认镜像与 CLI 变体

```text
sw-runtime                     Wine + Mono + Python + sw-install，不含 SWCLI
        │
        ├── sw-runtime:<版本>-cli
        │     链接同一个 swcli-payload
        │
        └── sw-preinstalled
              从官方介质安装纯净 SOLIDWORKS，不含 SWCLI
                    │
                    ├── sw-preinstalled:<版本>-cli
                    │     链接同一个 swcli-payload
                    │
                    └── sw-executable
                          加入测试补丁、FlexNet 与授权状态，不含 SWCLI
                                │
                                └── sw-executable:<版本>-cli
                                      链接同一个 swcli-payload
                                      │
                                      └── 真实导出 6 个产物通过后晋升
                    │
                    └── sw-preinstalled:<版本>-<语言>
                          通过 sw-preinstalled-language 增加官方语言资源
                          │
                          ├── sw-preinstalled:<版本>-<语言>-cli
                          │     链接同一个 swcli-payload
                          │
                          └── sw-executable:<版本>-<语言>
                                加入测试补丁、FlexNet 与授权状态
                                │
                                └── sw-executable:<版本>-<语言>-cli
                                      链接同一个 swcli-payload

swcli-payload                   高频：SWCLI 源码 + CLI 包装与 daemon entrypoint
        └── 由以上所有 -cli 镜像共享同一内容层
```

GHCR 只保留 `sw-runtime`、`sw-preinstalled`、`sw-executable` 三个 package。无后缀标签是可独立运行但不含 SWCLI 的默认镜像，例如 `sha-xxxxxxx`、`main`、`2025` 和 `latest`；同一镜像加入 SWCLI 后使用对应的 `-cli` 标签，例如 `sha-xxxxxxx-cli`、`main-cli`、`2025-cli` 和 `latest-cli`。本地化镜像将语言 tag 放在 `-cli` 之前，例如 `latest-zh-cn` 与 `latest-zh-cn-cli`。不可变 SHA 候选可按构建依赖顺序提前发布；所有可变标签仍须等待对应 `sw-executable:*cli` 完成真实导出后原子晋升。

## 安装 SOLIDWORKS

### 1. 校验安装介质

`sw-install` 接受挂载好的 ISO 目录或已解压目录。完整介质至少需要包含主 MSI 及配套 CAB、根目录 `Toolbox` 压缩包、VC++ x64 运行库、.NET 4.8 安装包及 `swloginmgr/SOLIDWORKS Login Manager.msi`。

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
- 脚本会读取主 MSI 的 `ProductVersion`，将内部更新码（例如 `33.150.0053` 中的 `150`）转换为产品年份与 Service Pack（`2025 SP5.0`），并在当前 Wine 用户注册表中写入对应的 EULA 接受标记；
- 未传入该参数时，脚本不会写入任何 EULA 接受标记，介质自身仍可能要求交互确认或拒绝继续安装；
- 该参数不会下载软件、授予许可证、配置序列号，也不能替代调用者审阅和遵守实际协议；
- 出于需要显式确认的考虑，`--accept-eula` **没有环境变量等价项**。

脚本随后会准备固定版本的 Wine-Mono COM 环境，安装 VC++ 与官方 Login Manager，验证真实托管 COM 注册，执行主 MSI，确认 `SLDWORKS.exe` 已产生，并检查 `SldWorks.Application`、`LocalServer32`、`VersionIndependentProgID` 和 TypeLib 均由 MSI 正确注册。安装日志默认写入权限受限的 `/var/log/sw-install`；日志可能包含 MSI 属性或序列号，应仅保存在可信私有环境。

> [!NOTE]
> 直接在一次性 `docker run --rm` 容器中安装不会保留结果。生产使用应在私有 Dockerfile 中执行安装，或将整个 `WINEPREFIX` 持久化。

### 3. 构建私有预安装镜像

本项目将镜像构建分为三个彼此独立的部分：[`preinstall/Dockerfile`](preinstall/Dockerfile) 只从官方安装介质生成不含 SWCLI 的 SOLIDWORKS 镜像，[`swcli/Dockerfile`](swcli/Dockerfile) 只生成当前 SWCLI 与 DockerSW 适配器组成的 payload，[`swcli/Dockerfile.delivery`](swcli/Dockerfile.delivery) 再把同一 payload 链接到 runtime、preinstalled 与 executable 镜像，生成对应的 `-cli` 变体。这样仅修改 SWCLI 时，不需要重新安装 SOLIDWORKS，也不会改变已有的大体积层。

官方 CI 通过命名 BuildKit context 将 `swwi/data`、`Toolbox`、`swloginmgr` 和必要的先决组件从 `preinstall/media` 只读传给安装阶段；安装完成后介质不会进入镜像层。不要把介质、序列号属性文件、许可文件或生成的安装日志提交到公开仓库。即使使用 BuildKit 临时挂载，也应只在可信私有 Builder 上构建，并按组织策略保护或清理构建缓存。

如需传入序列号或站点专用 MSI 属性，优先使用 `SW_MSI_PROPERTIES_FILE` 指向私有 CI Secret 文件，不要通过 Dockerfile 的 `ARG`、`ENV` 或公开构建日志传递。

## `sw-install` 参数与环境变量

| 命令行参数 | 环境变量 | 默认值 | 说明 |
|---|---|---|---|
| `--media PATH` | `SW_MEDIA_PATH` | 无 | 已挂载或解压后的完整安装介质目录；必填 |
| `--registry-dir PATH` | `SW_INSTALL_REGISTRY_DIR` | 空 | 主 MSI 前导入目录内的私有 `.reg` 文件 |
| `--msi PATH` | `SW_MSI_RELATIVE_PATH` | `swwi/data/solidworks.msi` | 相对于介质根目录的主 MSI 路径 |
| `--install-dir PATH` | `SW_TARGET_INSTALL_DIR` | 默认空（MSI 内部解析为 `C:\Program Files\SOLIDWORKS`） | Wine 虚拟 C 盘中的自定义安装路径；指定时自动通过 8.3 短路径规避 Wine 命令行空格转义限制 |
| `--property NAME=VALUE` | `SW_MSI_PROPERTIES_FILE` | 空 | 追加 MSI 属性；文件格式为每行一个 `NAME=VALUE` |
| `--log-dir PATH` | `SW_INSTALL_LOG_DIR` | `/var/log/sw-install` | 权限受限的安装日志目录 |
| `--timeout SECONDS` | `SW_INSTALL_TIMEOUT` | `10800` | 每个长时间安装步骤的超时秒数 |
| `--accept-eula` | 无 | 关闭 | 显式确认接受适用 EULA，并写入由介质版本推导的标记 |
| `--validate-only` | 无 | 关闭 | 只提取并校验介质，不运行 Wine |
| 无 | `SW_INSTALL_WPF_THEMES` | `true` | 是否从官方 .NET 4.8 包提取所需 WPF 主题组件 |
| 无 | `WINEPREFIX` | `/root/.wine` | 安装结果所在的 Wine 前缀 |

运行 `sw-install --help` 可查看当前命令行说明。

## 本地化镜像

英文仍是无语言后缀的默认镜像。CI 默认额外安装并验证简体中文资源，发布：

- `ghcr.io/yjbeetle/sw-preinstalled:latest-zh-cn`
- `ghcr.io/yjbeetle/sw-preinstalled:latest-zh-cn-cli`
- `ghcr.io/yjbeetle/sw-executable:latest-zh-cn`
- `ghcr.io/yjbeetle/sw-executable:latest-zh-cn-cli`

语言资源在核心 SOLIDWORKS 安装完成后，以独立 MSI 层加入；该层同时生成对应 UTF-8 locale，并通过 `LANG`/`LC_ALL` 让 Wine 中的 SOLIDWORKS 选择该语言。同一语言镜像同时供默认版本与 `-cli` 变体复用，不会重新安装 SOLIDWORKS。语言 MSI 只在对应缓存缺失时从 ISO 读取。每个本地化 `sw-executable:*cli` 会通过 COM 核对实际界面语言，并导出一个 STEP 文件后才晋升可变 tag。

手动运行工作流时，`languages` 接受逗号分隔的语言 tag，或使用 `all` 构建全部官方语言：

| Tag | 官方介质目录 | Tag | 官方介质目录 |
|---|---|---|---|
| `zh-cn` | `chinese-simplified` | `zh-tw` | `chinese` |
| `cs` | `czech` | `fr` | `french` |
| `de` | `german` | `it` | `italian` |
| `ja` | `japanese` | `ko` | `korean` |
| `pl` | `polish` | `pt-br` | `portuguese-brazilian` |
| `ru` | `russian` | `es` | `spanish` |
| `tr` | `turkish` |  |  |

## 自动化构建与验证流水线 (`build.yml`)

本项目提供完整的 GitHub Actions 单一持续集成流水线配置 [`.github/workflows/build.yml`](.github/workflows/build.yml)，实现原生 DAG 依赖与零多余网络开销的自动化交付：

1. **`unit-tests`**：递归检出固定 SWCLI submodule，校验 Docker 适配器与安装脚本；
2. **`build-and-smoke-test`**：在同一台 runner 与同一个 BuildKit content store 内完成全部镜像构建，避免 runtime 刚推送到 GHCR 又被下一台 runner 重复下载：
   - 构建不含 SWCLI 的 `sw-runtime` 与独立 `swcli-payload`，再通过通用 Delivery Dockerfile 组合为 `sw-runtime:*cli`，并验证两种镜像的能力边界；
   - 挂载 Google Drive，通过 `rclone` 开启 VFS 缓存稀疏读取官方 ISO；
   - 执行无人值守安装生成 `sw-preinstalled`，再加入当前 SWCLI payload 生成 `sw-preinstalled:*cli`；
   - 就地构建 `sw-executable` 与 `sw-executable:*cli`，后者执行真实 CAD 导出冒烟测试（验证 6 个 STEP、PDF、DWG 输出）；
   - 六个英文镜像及本地化变体分别使用 GHCR registry cache；仅修改 SWCLI 时会复用 Wine、SOLIDWORKS 安装、语言资源与测试运行时层；
   - 默认镜像与 CLI 镜像的 SHA 候选按后续 `FROM` 依赖顺序发布；**原子晋升发布**仍只在冒烟测试通过后为两套镜像同时晋升 `:latest`、`:latest-cli` 及对应分支标签。

### Google Drive Secret 配置

在 Google Cloud 中创建 OAuth Client ID、启用 Google Drive API，并在本地生成专供 CI 使用的 `gdrive` remote：

```bash
rclone config
rclone lsf 'gdrive:ISO所在目录'
```

确认能够列出介质后，将配置编码为单行 Base64：

```bash
rclone config show gdrive | base64 | tr -d '\n'
```

保存为 GitHub 仓库的 Actions Secret：

| Secret | 内容 |
|---|---|
| `RCLONE_CONFIG_B64` | `gdrive` remote 完整配置的单行 Base64 文本 |

[`.github/workflows/check-google-drive.yml`](.github/workflows/check-google-drive.yml) 会定期执行轻量目录探活，验证 Secret、OAuth Refresh Token 与目标文件仍然可访问。

### 手动触发构建流水线

可在 GitHub Actions 页面选择 `Build & Verify SolidWorks Images` 点击 `Run workflow`，或通过 GitHub CLI 触发：

```bash
gh workflow run build.yml --ref main
```

## 运行私有预安装镜像

### 1. 登录 GHCR 私有仓库 (PAT)

若将预安装镜像托管在 GHCR 私有镜像仓库，需使用具备 Package 权限的 **Personal Access Token (PAT)** 进行登录：

1. 打开浏览器访问 [GitHub Personal Access Tokens (Classic)](https://github.com/settings/tokens)，点击 **Generate new token -> Generate new token (classic)**；
2. 权限作用域（Scopes）仅需勾选：
   - **`read:packages`**；
3. 在目标宿主机（如 NAS 或本地机器）执行登录（将 `<YOUR_GITHUB_USERNAME>` 与 `<YOUR_GITHUB_PAT>` 替换为您自己的 GitHub 用户名和令牌）：

```bash
echo "<YOUR_GITHUB_PAT>" | docker login ghcr.io -u <YOUR_GITHUB_USERNAME> --password-stdin
```

### 2. 命令行执行导出

#### 模式 A：使用可执行镜像（内置测试许可，即开即用）

```bash
docker run --rm \
  -v "$(pwd):/workspace" \
  ghcr.io/yjbeetle/sw-executable:latest-cli \
  bash -lc 'sw-cli document open /workspace/model.SLDPRT --json &&
            sw-cli document export /workspace/dist/model.STEP --json &&
            sw-cli document close --discard --json'
```

#### 模式 B：使用纯净预装镜像（连接局域网 FlexNet 许可服务器）

```bash
docker run --rm \
  -e SW_LICENSE_SERVER=25734@192.168.1.100 \
  -v "$(pwd):/workspace" \
  ghcr.io/yjbeetle/sw-preinstalled:latest-cli \
  bash -lc 'sw-cli document open /workspace/model.SLDPRT --json &&
            sw-cli document export /workspace/dist/model.STEP --json &&
            sw-cli document close --discard --json'
```

### 3. 使用 SWCLI 建模与检查

DockerSW 镜像使用 Linux Python 运行 `sw-cli` 协议客户端，只在 Wine Windows
Python 中运行 daemon 与 COM worker。容器入口会在检测到已安装的 SOLIDWORKS
后显式执行一次 `sw-cli daemon start`；该命令自身会等待 daemon 与 SOLIDWORKS
就绪，已经运行时则幂等复用，不会重复启动。Linux 薄入口只负责选择对应的
Python 环境，typed 命令中的 Linux 路径由 `sw-cli` 客户端在已知的路径字段（如
`document.open` 的 `path`、`document.export` 的 `output`、`part.create-box`
的 `--template`）上调用 `SWCLI_PATH_TRANSLATE_CMD` 指向的 helper 转成 Wine
路径。命令语义、COM 类型处理、验证和 JSON 结果均来自同一份 SWCLI 源码。

```bash
sw-cli version --json
sw-cli doctor --json
sw-cli part create-box /workspace/box.SLDPRT \
  --width-mm 100 --height-mm 50 --depth-mm 20 --json
sw-cli document inspect --detail structure --json
sw-cli document diagnose --json
sw-cli document render /workspace/box.bmp \
  --view isometric --width 1024 --height 768 --json
sw-cli document close --json
```

`sw-cli document export` 只根据显式输出扩展名工作，不解释源文件命名规则。
`.REND.SLDASM -> GLB`、工程图同时导出 PDF/DWG 等策略由实际 CI 脚本组合
`document open/export/close` 完成，不进入 SWCLI 协议，也不再提供额外的
`sw-export` 包装层。普通导出允许源文档存在未保存或待重建状态，并仅在发现
这些问题时返回结构化 warnings；业务 CI 应使用 `--strict`，在生成正式产物前
要求源文档已保存、已重建且导出过程不改变其状态。

`sw-preinstalled:*cli` 与 `sw-executable:*cli` 启动时会显式执行
`sw-cli daemon start`，并等待 SOLIDWORKS 完成初始化后才执行容器命令。daemon 通过 Wine
已验证的 `DispatchEx` 激活路径创建独占实例，并在单一 COM worker 中串行执行
请求；默认使用隐藏模式且绝不会自动添加 `--attach-existing`。同一容器内的后续命令
复用该实例。若启动失败，入口会输出 `daemon start --json` 的完整错误并停止执行用户命令。

SWCLI payload 直接从父仓库锁定的 `swcli/SWCLI` 源码复制到 `/opt/swcli`，不会安装或
调用旧版 SWCLI wheel。Linux 客户端和 Wine Windows daemon 都通过 `PYTHONPATH` 优先加载
这份源码，因此镜像运行行为与子模块提交一致。

### 4. CI/CD 流水线集成示例 (GitLab CI)

在私有 GitLab Runner 中使用 `sw-preinstalled:*cli` 镜像导出 CAD 产物。源文件到目标
格式的规则直接属于该项目的 CI 配置：

```yaml
export_cad_assets:
  stage: export
  image: ghcr.io/yjbeetle/sw-preinstalled:latest-cli
  variables:
    SW_LICENSE_SERVER: "25734@192.168.1.100"  # 建议配置为 masked/protected CI/CD Variable
  script:
    - mkdir -p ./dist
    - sw-cli document open "$CI_PROJECT_DIR/model.SLDPRT" --json
    - sw-cli document export "$CI_PROJECT_DIR/dist/model.STEP" --strict --json
    - sw-cli document close --discard --json
  artifacts:
    paths:
      - ./dist/
```

> [!NOTE]
> 将 `SW_LICENSE_SERVER` 配置为 CI/CD 受保护变量，不要将内网地址或许可凭据直接硬编码提交到公开代码库。基础镜像 `sw-runtime` 本身不含 SOLIDWORKS 程序，仅供构建衍生镜像，不能直接用于真实 CAD 导出。

## 运行时环境变量

### 无头显示 (Display)

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `DISPLAY_RESOLUTION` | `1920x1080` | Xvfb 虚拟屏幕分辨率（形如 `1920x1080`、`2560x1440`） |
| `DISPLAY` | `:99` | 容器内 Xvfb 托管的虚拟屏幕编号 |

### VNC 人类监看

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `VNC_ENABLE` | `false` | 设为 `true` 时，在现有 Xvfb 桌面上启动 Openbox 与 x11vnc，并以可见模式启动 SOLIDWORKS |
| `VNC_VIEW_ONLY` | `true` | 只允许观看；设为 `false` 后允许远程键盘和鼠标输入，可能干扰自动化 |
| `VNC_PORT` | `5900` | x11vnc 监听端口 |
| `VNC_LISTEN` | `0.0.0.0` | x11vnc 在容器内的监听地址 |
| `VNC_PASSWORD` | 空 | 可选 VNC 密码；留空时会打印安全警告 |

默认不会启动 VNC。仅本机监看时，建议通过 `-p 127.0.0.1:5900:5900` 发布端口：

```bash
docker run --rm \
  -e VNC_ENABLE=true \
  -p 127.0.0.1:5900:5900 \
  ghcr.io/yjbeetle/sw-executable:latest-cli
```

daemon 通过 `DispatchEx` 创建独占 SOLIDWORKS 实例后，会等待官方
`StartupProcessCompleted` 状态再开始接收请求。已安装 SOLIDWORKS 的 `-cli` 镜像会在
entrypoint 中通过 `sw-cli daemon start` 预热 daemon，后续调用通过本地回环协议复用
同一个实例；若 daemon 意外退出，typed `sw-cli document` / `part` 命令会返回
`DaemonUnavailable`，不会隐式重启或退回直接 COM。SOLIDWORKS 启动等待上限默认为
120 秒，可通过 `SWCLID_START_TIMEOUT` 调整；单次导出请求默认仍有独立的 600 秒超时。
缺少 SOLIDWORKS 或 SWCLI 的默认/运行时镜像只记录跳过原因，不会因预热条件
不完整而启动失败。

### SWCLI daemon

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `SWCLI_ENDPOINT` | `127.0.0.1:18495` | SWCLI daemon 本地协议端点 |
| `SWCLID_START_TIMEOUT` | `120` | daemon 与 SOLIDWORKS 就绪等待秒数 |

容器自动启动只支持本地端点。对外暴露 daemon 属于显式部署行为，应直接运行
`sw-cli daemon serve --allow-remote`，并置于可信网络边界或认证隧道之后。

### 许可服务配置 (License)

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `SW_LICENSE_SERVER` | 空 | 远程 FlexNet 许可服务器（例如 `25734@192.168.1.100`）；配置后优先使用 |
| `SW_FLEXNET_DIR` | `/opt/SolidWorks_Flexnet_Server` | 本地 FlexNet 服务目录；未配置远程许可且目录下存在 `lmgrd.exe` 时自动拉起本地守护 |

## CI 真实导出门禁

[`.github/workflows/build.yml`](.github/workflows/build.yml) 直接负责启动容器、限制
总时长、收集日志并验证产物；容器内的 [`smoke-test/export.sh`](smoke-test/export.sh)
则只组合 typed SWCLI 命令，对四个官方样例执行 `open -> export -> close`，生成 6 个
STEP、PDF、DWG 产物。业务项目可以直接参考 `export.sh`，替换源文件、输出路径与
格式规则。随后 [`smoke-test/verify-swcli.sh`](smoke-test/verify-swcli.sh) 会在同一真实
SOLIDWORKS 会话中验证 capabilities Schema、更新戳、多文档切换和 lease 互斥。只有
这些门禁全部通过后，流水线才会晋升镜像。

## 测试

```bash
python3 -m unittest discover -s runtime/tests -p "test_*.py" -v
```

GitHub Actions 会递归检出固定 SWCLI submodule，构建真实容器，并校验固定 Wine/Wine-Mono 版本、stdcall 与托管 COM 修复、Windows Python/pywin32、`sw-install`，以及 Linux/Wine 两侧的 `sw-cli` 命令。SOLIDWORKS 与 Login Manager 的实际安装测试需要商业介质，因此应由持有合法介质的私有下游 CI 完成。

当前安装链主要按 SOLIDWORKS 2025 SP5.0 介质验证；其他版本的介质布局、安装属性或 Wine 行为可能不同，不能视为已经兼容。

## 许可与免责声明

1. 本项目是非官方兼容与自动化工具，与 Dassault Systèmes 或 SOLIDWORKS 无隶属、认可或支持关系；Wine 运行方式也不属于厂商官方支持的平台。
2. 本项目只提供通用 Wine 运行时、安装辅助、SWCLI 集成与 CI 验证脚本，不分发 SOLIDWORKS 商业软件、安装介质、序列号、许可文件或破解授权。
3. 使用者应自行确认其下载、安装、容器化、缓存、内部再分发和自动化使用方式符合适用的许可协议、合同与当地法律。
4. SOLIDWORKS 是 Dassault Systèmes 的注册商标。

# DockerSW 无头 Linux 容器化与 CI 自动化导出系统设计规格

## 1. 背景与设计目标

本项目 **DockerSW** 旨在提供一个专为 **Linux Docker 容器** 设计的、面向 **GitLab CI / Headless 无头批处理导出** 的 Wine 运行环境与自动化工具链：

1. **轻量纯粹**：专注提供无头执行与 COM 消息循环保障，确保高可靠、无弹窗阻塞的 CAD 文件批量自动化导出；
2. **安全合规的分层解耦架构**：
   - **公开运行时（`ghcr.io/yjbeetle/sw-runtime`）**：不包含任何 SOLIDWORKS 专有商业二进制文件、安装介质、序列号或许可服务器，也不预置 EULA 接受状态。默认标签提供固定版本验证的 Wine 64-bit、Wine-Mono、托管 COM 补丁、OpenGL 24-bit DIB 离屏渲染修复、Xvfb、Linux/Windows Python 环境与 `sw-install`；对应 `-cli` 标签额外加入 SWCLI；
   - **私有企业环境（下游构建与执行）**：使用者在自身可信基础设施中，通过合法取得的安装介质，使用 `sw-install` 执行官方静默安装并构建企业私有预安装镜像（`sw-preinstalled`），接入局域网浮动许可进行生产导出；
   - **默认镜像 / CLI payload 解耦交付**：`sw-runtime`、`sw-preinstalled`、`sw-executable` 固化低频变化的环境、安装与测试状态且不含 SWCLI；独立 `swcli-payload` 只包含当前 SWCLI 与 DockerSW 运行脚本；同一个通用 Delivery Dockerfile 将 payload 链接为对应的 `-cli` 变体；
3. **开箱即用的自动化导出**：由 GitLab CI / GitHub Actions 直接组合 SWCLI 的 typed `document open/export/close` 原子操作，支持 `.SLDPRT`/`.SLDASM` 导出 `.STEP`、`.SLDDRW` 导出 `.PDF` 和 `.DWG`、渲染装配体导出 `.GLB`；文件选择和命名规则归属具体 CI，不进入通用 CLI。

---

## 2. 系统架构与分层关系

```text
sw-runtime
  Wine + Mono + Python + pywin32 + sw-install；不含 SWCLI
  │
  ├── sw-runtime:<版本>-cli
  │     链接同一个 swcli-payload
  │
  └── sw-preinstalled
        从官方介质安装纯净 SOLIDWORKS；不含 SWCLI
        │
        ├── sw-preinstalled:<版本>-cli
        │     链接同一个 swcli-payload，用于生产导出
        │
        └── sw-executable
              加入测试补丁、FlexNet 与授权状态；不含 SWCLI
              │
              └── sw-executable:<版本>-cli
                    链接同一个 swcli-payload
                    └── 执行真实 CAD 导出门禁

swcli-payload
  SWCLI 源码 + CLI 包装与 daemon entrypoint；由所有 -cli 镜像共享同一内容层
```

每个仓库均发布不含 SWCLI 的不可变 `sha-xxxxxxx` 镜像，以及加入统一 payload 的 `sha-xxxxxxx-cli` 镜像。内部 payload 使用 `sha-xxxxxxx-payload`，不晋升可变标签；真实导出通过后，同时晋升默认镜像与 CLI 镜像的分支标签、`latest` 和 `latest-cli`。因此 CLI 高频变化只会生成一次 payload，并让各 CLI manifest 复用该内容层，不会触发 Wine、SOLIDWORKS 安装、语言资源和测试授权层重建；E2E 验证 CLI 镜像，而不是缓存本身。

---

## 3. 核心功能与模块详细设计

### 3.1 分层容器入口守护 (`runtime/entrypoint.sh` + `swcli/entrypoint-cli.sh`)

容器启动时执行以下标准化自适应与环境保障：

1. **兼容性补丁自检与动态注入**：
   - 自动检测并执行 `/usr/local/lib/sw-runtime/patch_win32u.pl`：修复 Wine 11.x 在 24-bit DIB 下 `wglMakeContextCurrent` 引起的无头离屏渲染黑屏与崩溃缺陷；
   - 自动检测并执行 `/usr/local/lib/sw-runtime/patch_wine_mono.pl`：修补 Wine-Mono CCW (`ComCallableWrapper`) 释放时的断言崩溃；
2. **Xvfb 无头显示守护**：
   - 检测并拉起 `Xvfb ${DISPLAY:-:99} -screen 0 1024x768x24 -ac +extension GLX +render -noreset`；
   - 保证 Wine COM 体系与 SOLIDWORKS 宿主窗口消息泵具备合法的图形显示后端；
3. **可选 VNC 人类监看层**：
   - 默认不启动；设置 `VNC_ENABLE=true` 后，由 entrypoint 在现有 Xvfb 桌面上启动 Openbox 与 x11vnc；
   - `VNC_VIEW_ONLY=true` 默认为只读监看，不改变 SWCLI、COM 或导出行为；显式关闭后才接受远程键盘和鼠标输入；
   - 未设置 `VNC_PASSWORD` 时发出安全警告，推荐只向宿主机回环地址发布 VNC 端口；
4. **Wine-Mono 与托管 COM 运行时支持**：
   - 校验 Wine-Mono 并在全新前缀初始化时自动完成静默配置；
   - 执行 `prepare_managed_com.sh`，确保 x86/x64 托管 RegAsm、`RegistrationServices` 与 `stdole` 正确注册，消除 .NET 插件加载时的 COM 错误；
5. **统一原生预装模型**：
   - 彻底摒弃容易缺失注册表与 COM 组件的免安装目录挂载机制；所有环境均基于 `sw-install` 进行 100% 完整原版无人值守安装，主程序严格位于虚拟 C 盘（`drive_c/Program Files/SOLIDWORKS`），保证 COM 类映射与注册表完整可用；
6. **许可服务智能判定与开关（私有环境专有配置）**：
   - **远程网络许可模式（推荐）**：在私有镜像构建期固化或私有 CI 运行时注入环境变量 `SW_LICENSE_SERVER`（如 `25734@10.0.0.1`），容器自动注入 `FLEXlm License Manager` 与系统环境变量，无需在容器内跑常驻许可进程；
   - **本地自启许可模式（按需）**：在私有构建期内置或运行时挂载到 `SW_FLEXNET_DIR`（默认 `/opt/SolidWorks_Flexnet_Server`），只要目录下存在 `lmgrd.exe` 与许可文件即自动在后台拉起守护并等待端口就绪；
7. **命令生命周期与构建支持**：
   - 支持 `--init-only` 参数，在 Docker 构建期刷新并持久化 Wine 注册表后干净退出；
   - 同时检测到 SOLIDWORKS 与 SWCLI 时，默认通过 `sw-cli daemon serve` 启动并等待 daemon 与 COM worker 就绪；任一组件缺失的默认/运行时镜像自动跳过；
   - 支持透明传递任意执行命令（如 `sw-cli`、`sw-install` 或 `bash`）。

### 3.2 官方介质安装引擎 (`sw-install`)

为了彻底解决挂载纯文件时丢失庞大 COM 注册表与依赖环境的问题，设计了独立的标准安装工具 `sw-install`：

1. **介质结构自动检测与校验**：
   - 支持已挂载的 ISO 介质目录或已解压目录；
   - 验证关键核心组件完备性：主安装包 MSI、VC++ 运行库、.NET 4.8 框架以及 `swloginmgr/SOLIDWORKS Login Manager.msi`；
   - 提供 `--validate-only` 模式，用于在无头 CI 中仅做介质合法性校验；
2. **严格明确的 EULA 确认模型**：
   - 遵循版权与法律边界规范，公开运行时不预设任何 EULA 接受标记；
   - 必须由调用者显式传入 `--accept-eula` 参数（**不设环境变量以强制显式确认**）；
   - 自动解析主 MSI 的 `ProductVersion`，计算对应产品年份与 Service Pack，在 Wine 注册表中动态写入官方接受键值；
3. **真实 COM 环境与登录组件安装**：
   - 静默安装官方 Login Manager，确保真实托管 COM 接口注入注册表；
   - 静默调用主程序 MSI 执行安装，依赖官方 MSI 安装脚本生成完整的 `SldWorks.Application`、`LocalServer32`、TypeLib 及 ProgID 注册；
   - 安装完成后自动运行健全性检查：验证 `SLDWORKS.exe` 文件存在且关键 COM 注册表节点齐全；
4. **私有镜像构建隔离**：
   - 配合 BuildKit 挂载机制（`--mount=type=bind`），安装介质在镜像构建完成后不会残留在任何镜像层中，保证产物整洁。

### 3.3 SWCLI 与 CI 导出组合 (`sw-cli`)

1. **Linux / Windows 路径智能透明转换**：
   - `sw-cli` 客户端在发送 typed 请求前，只对已知的路径字段（`path`、`output`、`template`）做转换；不依赖参数位置；
   - DockerSW 薄入口 `sw-cli` 导出 `SWCLI_PATH_TRANSLATE_CMD=/usr/local/bin/linux-to-wine-path`，helper 将 POSIX 路径交给 `winepath -w`（例如 `/workspace/model.SLDPRT` -> `Z:\workspace\model.SLDPRT`），已是盘符形式的 Windows 路径原样透传；
   - 未设置该环境变量时（如原生 Windows 或 macOS-Wine 直连），客户端不做任何转换；
2. **职责边界**：
   - typed 建模、检查、重建、渲染与原子导出均由独立 SWCLI 项目维护；
   - `sw-cli document export` 只根据显式输出扩展名选择 STEP、GLB、PDF 或 DWG，不解释源文件名；
   - manifest、`.REND.SLDASM -> GLB` 及输出命名属于具体项目的 CI 配置，不进入 SWCLI；
   - DockerSW 只提供 daemon 预热、容器生命周期适配以及指向翻译 helper 的环境变量，不再解析 CLI 参数位置；
3. **常驻 daemon 与 Wine COM worker**：
   - `sw-preinstalled:*cli` 与 `sw-executable:*cli` 的 entrypoint 默认执行 `sw-cli daemon serve` 并等待就绪，后续调用通过 `127.0.0.1` 回环端点复用同一个实例；
   - daemon 默认拒绝监听非回环地址；DockerSW 只有在 `SWCLID_ALLOW_REMOTE=true` 时才传入显式放行参数，该参数不提供认证，必须配合可信网络边界或安全隧道；
   - entrypoint 将 SOLIDWORKS 启动期限与健康探测余量纳入同一个总 deadline，避免一次阻塞探测让容器启动无限超期；
   - Docker 中由 entrypoint 负责 daemon 生命周期；typed 命令只连接已有服务，daemon 意外退出时明确失败；
   - daemon 使用 `win32com.client.DispatchEx("SldWorks.Application")` 获取独占实例，规避 Wine 下 `GetActiveObject` 对直接启动进程的不可靠行为；
   - 按官方 `StartupProcessCompleted` 状态等待启动加载完成，再开放协议端点，避免 COM 已返回但启动插件尚未就绪的竞态；
   - supervisor 与 COM worker 分进程，worker 在单一 COM apartment 中串行执行全部请求；调用超时后会连同未知状态的 SOLIDWORKS 进程树一起替换；
   - DockerSW 仅负责 Linux/Wine 路径转换、daemon 预热和容器生命周期，协议、worker 与 typed operations 均由 SWCLI 拥有；
4. **CI 导出策略**：
   - CI 根据项目规则选择源文件，并显式指定每一个输出路径和扩展名；
   - 当前真实门禁将 `.SLDPRT` / `.SLDASM` 导出为 `.STEP`，将 `.SLDDRW` 导出为 `.PDF` 与 `.DWG`；
   - 若业务 CI 需要 `*.REND.SLDASM -> .GLB`，同样直接调用原子 `document export`；
5. **CI 安全语义**：
   - GitHub Actions workflow 直接负责容器生命周期、总超时、日志与产物收集，不保留单一消费者的包装脚本；
   - `smoke-test/export.sh` 是容器内可复制的使用范例，直接按业务规则排列 typed SWCLI 命令；
   - 在启动 SOLIDWORKS 前完成缺失输入、目标冲突和覆盖策略预检；
   - 每个文档执行 typed open/export/close，关闭失败时中止后续项目；
   - 产物必须通过非空和文件签名验证；任一失败返回退出码 `1`。

---

### 3.4 交互式图形能力

DockerSW 保留不依赖旧 `sw-daemon` 的人类监看能力。设置 `VNC_ENABLE=true` 后，容器入口会为现有 Xvfb 桌面启动 Openbox 与 x11vnc；默认 `VNC_VIEW_ONLY=true`，因此远程客户端只能观察 SOLIDWORKS 窗口。该能力只属于 Docker/Wine 运行环境，不进入 SWCLI，也不参与 SOLIDWORKS COM 生命周期。

---

## 4. 关键底层兼容机制（Wine & Graphics）

1. **Wine 11.x 24-bit DIB 离屏 OpenGL 渲染修复**：
   - *问题*：Xvfb 默认屏幕深度为 24bpp，Wine 11.x 的 `win32u.so` 在处理 24-bit DIB 时缺乏像素格式转换支持，导致离屏 OpenGL 交换缓冲失败，SOLIDWORKS 导出包含 3D 内容的模型或渲染时产生全黑图或抛出内存段错误。
   - *方案*：通过 `patch_win32u.pl` 补丁在内存/二进制层将 24-bit DIB 请求透明提升为支持硬件加速与双缓冲的 32-bit DIB 上下文，彻底恢复 OpenGL 离屏绘图能力。
2. **Wine-Mono 托管 COM 注册与 CCW 补丁**：
   - *问题*：SOLIDWORKS 大量依赖 .NET 互操作及官方 Login Manager，Wine-Mono 原生环境在注册 CCW 接口或释放接口引用计数时可能触发断言中断。
   - *方案*：集成 MacSW 验证补丁体系，并结合 `patch_wine_mono.pl` 修正 CCW release 断言，使托管 COM 在无头容器中稳定运转。

---

## 5. 规格检查与验证规范

- [x] **架构一致性**：公开基础镜像 `sw-runtime` 与私有安装镜像 `sw-preinstalled` 职责彻底分离；
- [x] **版权合规性**：公开仓库无任何商业软件实体与许可凭据，EULA 坚持调用方显式确认原则；
- [x] **命名规范性**：全局统一使用标准命令名 `sw-install` 与 `sw-cli`，环境变量全项目对齐（`SW_INSTALL_DIR`, `SW_LICENSE_SERVER`, `SW_FLEXNET_DIR`）；
- [x] **运行健壮性**：无头环境具备 Xvfb、OpenGL 24-bit 离屏渲染与 Wine-Mono 托管 COM 的三重稳定性保障。

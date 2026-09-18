# DockerSW 无头 Linux 容器化与 CI 自动化导出系统设计规格

## 1. 背景与设计目标

本项目 **DockerSW** 旨在提供一个专为 **Linux Docker 容器** 设计的、面向 **GitLab CI / Headless 无头批处理导出** 的 Wine 运行环境与自动化工具链：

1. **轻量纯粹**：专注提供无头执行与 COM 消息循环保障，确保高可靠、无弹窗阻塞的 CAD 文件批量自动化导出；
2. **安全合规的分层解耦架构**：
   - **公开基础运行时（`ghcr.io/yjbeetle/sw-runtime`）**：不包含任何 SOLIDWORKS 专有商业二进制文件、安装介质、序列号或许可服务器，也不预置 EULA 接受状态。仅提供固定版本验证的 Wine 64-bit、Wine-Mono、托管 COM 补丁、OpenGL 24-bit DIB 离屏渲染修复、Xvfb 无头虚拟显示、Windows Python + pywin32 环境以及 `sw-install` 和 `sw-export` 工具链；
   - **私有企业环境（下游构建与执行）**：使用者在自身可信基础设施中，通过合法取得的安装介质，使用 `sw-install` 执行官方静默安装并构建企业私有预安装镜像（`sw-preinstalled`），接入局域网浮动许可进行生产导出；
3. **开箱即用的自动化导出**：提供统一的 `sw-export` 命令行工具，原生适配 GitLab CI / GitHub Actions 流水线，支持 `.SLDPRT`/`.SLDASM` 导出 `.STEP`、`.SLDDRW` 导出 `.PDF` 和 `.DWG`、渲染装配体导出 `.GLB`。

---

## 2. 系统架构与分层关系

```
┌────────────────────────────────────────────────────────────────────────┐
│                        公开开源环境 (GitHub Actions)                    │
│                                                                        │
│               [ 公开 Base 镜像: ghcr.io/yjbeetle/sw-runtime:latest ]    │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Ubuntu 22.04 LTS x86_64                                          │  │
│  │  ├─ Xvfb (:99 虚拟屏幕, 1024x768x24, 提供 COM 消息循环保障)         │  │
│  │  ├─ Wine 11.16 运行时 (集成 win32u 24-bit DIB OpenGL 离屏修复补丁) │  │
│  │  ├─ Wine-Mono 11.3.0 (集成托管 COM、stdcall 与 CCW 断言修复补丁)   │  │
│  │  ├─ Windows Python 3.11 + pywin32 运行时                          │  │
│  │  ├─ sw-install：官方介质校验、静默安装与 MSI COM 注册验证工具       │  │
│  │  └─ sw-export：无头静默批量导出 CLI (基于 win32com)              │  │
│  │  ※ 纯净底座：不含商业软件实体、不预设许可、不预设 EULA              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ 作为 Base 镜像拉取
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   企业私有构建环境 (Private CI Builder)                 │
│                                                                        │
│  合法商业安装介质 (ISO/目录)                                           │
│         │                                                              │
│         ├─► sw-install --media <ISO> --accept-eula                     │
│         │   (完成 VC++、Login Manager、主 MSI 安装与真实 COM 注册)     │
│         ▼                                                              │
│  [ 企业私有预安装镜像: sw-preinstalled:latest ]                        │
│                                                                        │
│  ※ 许可配置全部可在构建期就绪（生成开箱即用的自包含镜像）：            │
│     ├─ 方案 1（网络许可）：Dockerfile 指定 ENV SW_LICENSE_SERVER=...   │
│     └─ 方案 2（本地许可）：COPY lmgrd+lic 并 ENV START_LOCAL_LICENSE=true│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ 运行 (docker run / CI Runner)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│               生产导出流水线 (GitLab CI / 内部批处理 Runner)            │
│                                                                        │
│  ※ 极简开箱即用：镜像内已预置许可与程序，无需额外配置，直接批处理导出   │
│     sw-export --list /workspace/export-manifest.txt                    │
│                                                                        │
│  （可选覆盖）：多环境切换时仍支持私有 CI 变量覆盖 SW_LICENSE_SERVER    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心功能与模块详细设计

### 3.1 基础运行时与容器入口守护 (`entrypoint.sh`)

容器启动时执行以下标准化自适应与环境保障：

1. **兼容性补丁自检与动态注入**：
   - 自动检测并执行 `/usr/local/lib/sw-runtime/patch_win32u.pl`：修复 Wine 11.x 在 24-bit DIB 下 `wglMakeContextCurrent` 引起的无头离屏渲染黑屏与崩溃缺陷；
   - 自动检测并执行 `/usr/local/lib/sw-runtime/patch_wine_mono.pl`：修补 Wine-Mono CCW (`ComCallableWrapper`) 释放时的断言崩溃；
2. **Xvfb 无头显示守护**：
   - 检测并拉起 `Xvfb ${DISPLAY:-:99} -screen 0 1024x768x24 -ac +extension GLX +render -noreset`；
   - 保证 Wine COM 体系与 SOLIDWORKS 宿主窗口消息泵具备合法的图形显示后端；
3. **Wine-Mono 与托管 COM 运行时支持**：
   - 校验 Wine-Mono 并在全新前缀初始化时自动完成静默配置；
   - 执行 `prepare_managed_com.sh`，确保 x86/x64 托管 RegAsm、`RegistrationServices` 与 `stdole` 正确注册，消除 .NET 插件加载时的 COM 错误；
4. **统一原生预装模型**：
   - 彻底摒弃容易缺失注册表与 COM 组件的免安装目录挂载机制；所有环境均基于 `sw-install` 进行 100% 完整原版无人值守安装，主程序严格位于虚拟 C 盘（`drive_c/Program Files/SOLIDWORKS`），保证 COM 类映射与注册表完整可用；
5. **许可服务智能判定与开关（私有环境专有配置）**：
   - **远程网络许可模式（推荐）**：在私有镜像构建期固化或私有 CI 运行时注入环境变量 `SW_LICENSE_SERVER`（如 `25734@10.0.0.1`），容器自动注入 `FLEXlm License Manager` 与系统环境变量，无需在容器内跑常驻许可进程；
   - **本地自启许可模式（按需）**：在私有构建期直接内置 `lmgrd.exe`+许可文件或在运行时挂载 `/opt/SolidWorks_Flexnet_Server`，并配置 `START_LOCAL_LICENSE=true`，后台拉起 `lmgrd.exe` 并等待端口就绪；
6. **命令生命周期与构建支持**：
   - 支持 `--init-only` 参数，在 Docker 构建期刷新并持久化 Wine 注册表后干净退出；
   - 支持透明传递任意执行命令（如 `sw-export`、`sw-install` 或 `bash`）。

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

### 3.3 无头静默批量导出引擎 (`sw-export` / `export_sw.py`)

1. **Linux / Windows 路径智能透明转换**：
   - 脚本接收 Linux 格式的文件清单（支持绝对路径与相对路径）；
   - 自动转换为 Wine 虚拟 Windows 盘符路径（如 `/workspace/model.SLDPRT` -> `Z:\workspace\model.SLDPRT`，或 C 盘相对映射）；
2. **静默调用与防阻塞设计**：
   - 通过 `win32com.client.DispatchEx("SldWorks.Application")` 获取独立 COM 实例；
   - 强制设置 `UserControl = False` 与 `Visible = False`；
   - 打开模型使用 `OpenDoc6` 并传入 `swOpenDocOptions_Silent`（值为 1），阻断所有 GUI 确认弹窗；
   - 导出使用 `model.Extension.SaveAs3`，指定 `swSaveAsOptions_Silent`；
   - 导出后显式调用 `CloseDoc` 释放内存，批量处理完成后安全调用 `sw_app.ExitApp()`；
3. **导出格式映射体系**：
   - `.SLDPRT` / `.SLDASM` -> 导出为工业标准 `.STEP`
   - `.SLDDRW` -> 导出为工程图 `.PDF` 与 `.DWG`
   - `*.REND.SLDASM` -> 导出为 Web 3D 呈现格式 `.GLB`
4. **CI 退出码与错误容忍机制**：
   - 清单中单个文件导出失败不中断流程，记录告警日志并继续处理后续模型；
   - 统计成功与失败总数；若存在失败项目则返回退出码 `1`，全部成功返回 `0`，与 CI/CD 流水线状态深度集成。

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
- [x] **命名规范性**：全局统一使用标准命令名 `sw-install` 与 `sw-export`，环境变量全项目对齐（`SW_INSTALL_DIR`, `SW_LICENSE_SERVER`, `START_LOCAL_LICENSE`）；
- [x] **运行健壮性**：无头环境具备 Xvfb、OpenGL 24-bit 离屏渲染与 Wine-Mono 托管 COM 的三重稳定性保障。

# DockerSW 无头 Linux 容器化与 CI 自动化导出系统设计规格

## 1. 背景与目标

当前 SolidWorks 主要运行在 Windows 物理机或虚拟机中。在现代 DevOps 与自动化制造流水线（CI/CD）中，依赖带图形界面的 Windows 节点（如 Windows Runner）存在资源开销大、难以并发扩容、授权维护复杂等痛点。
在 macOS 下的 WineSW 项目探索中，虽然实现了 Wine 运行 SolidWorks，但包含了大量针对 macOS 独有视口（Metal/CAMetalLayer）、窗口层级、中文 UI 字体替换等复杂的图形修复代码。

本项目 **DockerSW** 旨在提供一个专为 **Linux Docker 容器** 设计的、最精简的、面向 **GitLab CI / Headless 无头批处理导出** 的 Wine 运行环境：
1. **彻底剥离 UI 冗余**：不包含任何 macOS 视口避让守护、双缓冲剥离、字体软链接等修饰逻辑；
2. **两阶段解耦架构**：
   - **公开基础仓库（DockerSW）**：不含任何 SolidWorks 专有商业二进制代码，仅提供 Wine 64-bit、Xvfb 无头显示、Windows Python + pywin32 环境、无头注册表预配、智能入口与导出工具；由 GitHub Actions 自动化构建并推送到 GHCR；
   - **私有企业环境（下游使用方）**：通过挂载 Volume 或构建极简的下游私有镜像（`FROM ghcr.io/yjbeetle/dockersw:latest`）提供 SolidWorks 实体文件和 FlexNet 许可服务器；
3. **开箱即用的自动化导出**：提供完善的 `dockersw-export` 命令行工具，适配 GitLab CI 流水线，支持 `.SLDPRT`/`.SLDASM` 导出 `.STEP`、`.SLDDRW` 导出 `.PDF` 和 `.DWG`、渲染装配体导出 `.GLB`。

---

## 2. 系统架构与交互关系

```
               [ GitHub Actions 构建与发布 ]
                             │
                             ▼
         [ Docker 镜像: ghcr.io/yjbeetle/dockersw:latest ]
         ┌──────────────────────────────────────────────┐
         │ Ubuntu 22.04 LTS x86_64                      │
         │  ├─ Xvfb (:99 无头虚拟屏幕, COM 消息循环保障)  │
         │  ├─ Wine 64-bit 运行时环境                   │
         │  ├─ Windows Python 3.11 + pywin32            │
         │  ├─ 无头注册表预配 (EULA/禁用登录/禁用崩溃)   │
         │  └─ dockersw-export 统一导出 CLI 工具        │
         └──────────────────────┬───────────────────────┘
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼ 运行方式 A: Volume 挂载                        ▼ 运行方式 B: 极简私有镜像
┌────────────────────────────────┐              ┌────────────────────────────────┐
│ GitLab CI Runner / Docker      │              │ 企业私有 Docker 镜像           │
│ docker run -v /data/SW:/opt/sw │              │ FROM ghcr.io/.../dockersw      │
│  -e SW_LICENSE_SERVER=...      │              │ COPY ./sw /opt/solidworks      │
│  ghcr.io/yjbeetle/dockersw     │              │ ENV START_LOCAL_LICENSE=true   │
└────────────────────────────────┘              └────────────────────────────────┘
```

---

## 3. 核心功能与模块设计

### 3.1 容器入口守护与智能环境自适应 (`entrypoint.sh`)
容器启动时执行以下标准化检测与适配：
1. **Xvfb 无头显示守护**：检测并后台启动 `Xvfb :99 -screen 0 1024x768x24 -ac +extension GLX +render -noreset`，导出 `DISPLAY=:99`，为 Wine COM 与 SolidWorks 消息循环提供虚拟窗口环境；
2. **SolidWorks 程序挂载链接**：
   - 检查环境变量 `SW_INSTALL_DIR`（默认 `/opt/solidworks`）；
   - 若存在，自动在 Wine 虚拟 C 盘中建立软链接：`drive_c/Program Files/SOLIDWORKS Corp/SOLIDWORKS` -> `$SW_INSTALL_DIR`；
   - 自动注册关键 COM 依赖：`sldshellutils.dll`, `sldsearchcore.dll`；
3. **许可服务智能判定与开关**：
   - **远程许可模式**：若指定环境变量 `SW_LICENSE_SERVER`（例如 `25734@10.0.0.1`），动态注入注册表指向该服务器，跳过本地守护；
   - **本地自启模式**：若环境变量 `START_LOCAL_LICENSE=true`（或未指定远程服务器且检测到 `/opt/SolidWorks_Flexnet_Server/lmgrd.exe`），自动在后台拉起 `lmgrd.exe` 并等待端口监听就绪，注册表指向 `25734@127.0.0.1`；
4. **命令分发**：若传入参数则执行传入命令（如 `dockersw-export` 或 bash），若无参数则默认打印就绪状态并保活或退出。

### 3.2 无头静默导出引擎 (`export_sw.py` & `dockersw-export`)
1. **Linux / Windows 路径智能透明转换**：
   - 脚本接收 Linux 格式的文件清单（支持相对路径与绝对路径）；
   - 自动在内部转换为 Wine 可识别的 Windows 格式路径（如 `/workspace/foo.SLDPRT` -> `Z:\workspace\foo.SLDPRT`）；
2. **静默调用与防阻塞设计**：
   - 通过 `win32com.client.DispatchEx("SldWorks.Application")` 获取独立 COM 实例；
   - 强制设置 `UserControl = False` 与 `Visible = False`；
   - 打开文档使用 `OpenDoc6`，指定 `swOpenDocOptions_Silent`（值为 1），禁止弹窗；
   - 导出文档使用 `model.Extension.SaveAs3`，指定 `swSaveAsOptions_Silent`；
   - 导出完成后显式调用 `sw_app.CloseDoc(model_title)`，防止内存泄漏；
3. **导出格式映射**：
   - `.SLDPRT` / `.SLDASM` -> 导出 `.STEP`
   - `.SLDDRW` -> 导出 `.PDF` 和 `.DWG`
   - `*.REND.SLDASM` -> 导出 `.GLB`
4. **异常容错与 CI 退出码机制**：
   - 清单中单项失败记录错误并继续处理下一项；
   - 最终输出成功与失败数量汇总；若有任何一项失败则退出码为 1，全部成功则为 0。

### 3.3 CI 流水线与交付物
1. **GitHub Actions (`.github/workflows/docker-build.yml`)**：
   - 自动触发构建；
   - 包含容器健康自检 step（Wine 验证、Windows Python 导入 `win32com.client` 验证）；
   - 推送至 `ghcr.io/yjbeetle/dockersw`；
2. **文档与范例**：
   - `examples/docker-compose.yml`：展示本地/自建宿主机如何使用 Volume 挂载和环境变量测试导出；
   - `examples/gitlab-ci/.gitlab-ci.yml`：展示在 GitLab CI 中如何无缝集成；
   - `examples/private-image/Dockerfile`：展示如何封装私有镜像；
   - `examples/export-list-demo.txt`：标准清单范例；
   - `README.md`：详细的中英文操作说明。

---

## 4. 规格自检清单

- [x] **占位符检查**：无任何未确定项或 TODO，所有环境变量名、文件路径和 COM 参数均有明确值；
- [x] **版权合规**：仓库不包含任何 SolidWorks 二进制或许可文件，全部通过运行期挂载或私有镜像注入；
- [x] **范围检查**：不涉及任何 UI 调整、字体修饰或视口隔离，专注无头批处理与 CI 导出；
- [x] **一致性检查**：环境变量命名全项目对齐（`SW_INSTALL_DIR`, `START_LOCAL_LICENSE`, `SW_LICENSE_SERVER`）。

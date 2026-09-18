# DockerSW CLI 与常驻 Daemon 交互子系统设计规范

**文档版本：** 1.0.0  
**设计日期：** 2026-09-18  
**状态：** 待审查 (Pending Review)

---

## 1. 背景与目标

### 1.1 现状与痛点
SolidWorks 自身作为原生 Windows 桌面 CAD 软件，其所有官方操作入口和交互界面高度依赖图形界面（GUI）。尽管其底层具备非常完备的 COM/Automation API（如 `SldWorks.Application`、`IModelDoc2` 等），但官方并未提供现代化的命令行（CLI）交互接口或结构化数据通道：
1. **冷启动沉重**：每次通过 COM 启动 `SLDWORKS.exe` 进程耗时高达 15~30 秒，无法支撑频繁的自动化脚本与极速交互。
2. **缺乏结构化输入输出**：发生重建错误、特征告警或弹窗时，原生进程会挂起或直接弹出模态对话框，无法直接返回结构化错误码（exit code）与 JSON 数据。
3. **AI Agent 难以接入**：现代 AI 编码助手（如 Claude、Cursor、Antigravity）或外部自动化平台需要低延迟、支持动态代码执行、具备结构化感知与安全监控的统一接口。

### 1.2 建设目标
在 DockerSW 容器中构建一套一体化的 **CLI 与常驻守护进程（Daemon）交互子系统**：
- **常驻单例 Daemon (`sw-daemon`)**：在 Wine 环境中后台常驻持有 `SldWorks.Application` COM 实例，消除冷启动时间，实现亚秒级响应。
- **一等公民 CLI 客户端 (`sw-cli`)**：作为 Linux 容器原生命令，支持动态执行 Python 脚本（`sw-cli run`）、行内表达式求值（`sw-cli eval`）以及状态自省。
- **自动化上下文注入**：为执行的脚本自动注入 `swApp`、`args`、`set_output()` 及路径转换工具，极大简化自动化脚本与 AI 生成代码的复杂度。
- **结构化输出与 AI 就绪**：全命令支持 `--json` 输出，提供统一的 Schema（含 `stdout`、`stderr`、`exit_code`、`data`、`duration_ms`），为未来平滑演进为 **MCP (Model Context Protocol) Server** 奠定坚实协议基础。
- **VNC 监看模式**：支持伴随 Daemon 开启 VNC 监看，**默认采用 View-Only 只看模式（`-viewonly`）**，防止鼠标键盘意外干扰自动化流程；同时提供 `--vnc-interactive` 供人工接管调试。
- **冒烟测试与屏幕捕获**：提供屏幕截图指令（`sw-cli screenshot`），在无头 CI 冒烟测试中捕获当前 GUI 窗口状态并保存为图像产物，供持续集成归档与可视化复核。

---

## 2. 架构设计与核心组件

系统分为三层：**Linux 客户端命令层**、**本地回环 IPC 通信层**、以及 **Wine Windows 守护执行层**。

```
+-------------------------------------------------------------------------+
| Linux 容器环境                                                           |
|                                                                         |
|  +-------------------+        +--------------------------------------+  |
|  |     sw-cli        |        |              sw-daemon               |  |
|  | (run/eval/status) |        | (start/stop/restart/status --vnc)    |  |
|  +---------+---------+        +-------------------+------------------+  |
|            |                                      |                     |
|            | HTTP POST (JSON-RPC)                 | 管理子进程生命周期    |
|            v (127.0.0.1:18282)                    v                     |
|  +-------------------------------------------------------------------+  |
|  | Wine / Windows Python 3.11 环境                                    |  |
|  |                                                                   |  |
|  |   +-------------------------------------------------------------+ |  |
|  |   | daemon_server.py (HTTP Server)                              | |  |
|  |   |                                                             | |  |
|  |   |  - COM 初始化与全局持有: swApp = SldWorks.Application        | |  |
|  |   |  - 执行沙盒注入: swApp, args, set_output(), to_win_path()    | |  |
|  |   |  - stdout/stderr 流捕获与看门狗超时监控                      | |  |
|  |   +-----------------------------+-------------------------------+ |  |
|  |                                 |                                 |  |
|  |                                 v                                 |  |
|  |                   +---------------------------+                   |  |
|  |                   |   SLDWORKS.exe (常驻)     |                   |  |
|  |                   +---------------------------+                   |  |
|  +-------------------------------------------------------------------+  |
|                                                                         |
|  +-------------------------------------------------------------------+  |
|  | 显示与监看环境                                                     |  |
|  |   - Xvfb (Display :99)                                            |  |
|  |   - x11vnc (可选监看端口 5900; 默认 -viewonly 只看模式)             |  |
|  |   - 截图抓取 (X11 / import / xwd -> PNG 产物输出)                  |  |
|  +-------------------------------------------------------------------+  |
+-------------------------------------------------------------------------+
```

---

## 3. 详细设计与协议规范

### 3.1 Wine 守护服务端 (`daemon_server.py`)

1. **协议与绑定**：
   - 采用标准库 `http.server`，绑定 `127.0.0.1:18282`（仅限容器本地回环，避免外部端口暴露）。
2. **COM 初始化与管理**：
   - 启动时调用 `pythoncom.CoInitialize()`。
   - 通过 `win32com.client.DispatchEx("SldWorks.Application")` 获取实例。
   - 依据启动模式设置可见性：无头模式下 `swApp.Visible = False`；若传入 `--visible`（如开启 VNC 监看），则设置 `swApp.Visible = True`。
   - 统一配置 `swApp.UserControl = False`，并设置静默首选项以压制所有模态对话框。
3. **接口定义**：
   - `GET /v1/health`：
     - 返回：`{"status": "ok", "ready": true, "sw_connected": true, "version": "...", "uptime_s": 12.3}`。
   - `POST /v1/execute`：
     - 请求体：
       ```json
       {
         "code": "print('Document:', swApp.ActiveDoc.GetTitle() if swApp.ActiveDoc else 'None')\nset_output({'count': 42})",
         "args": ["--mode", "fast"],
         "timeout": 60
       }
       ```
     - 响应体：
       ```json
       {
         "success": true,
         "exit_code": 0,
         "stdout": "Document: None\n",
         "stderr": "",
         "data": { "count": 42 },
         "duration_ms": 35
       }
       ```
   - `POST /v1/canvas`：
     - 请求体：`{"target_path": "Z:\\tmp\\canvas.png"}`（可指定保存路径，缺省时自动生成临时文件）
     - 行为：调用当前活动文档 `swApp.ActiveDoc.Extension.SaveAs3(path, 0, 1, ...)`，直接将当前 3D 画布渲染为纯净 PNG 图像（无 UI 杂质）。
     - 响应体：`{"success": true, "path": "...", "doc_title": "part1.SLDPRT"}`。
   - `POST /v1/screenshot`：
     - 请求体：`{"target_path": "Z:\\tmp\\screen.png"}`
     - 响应体：`{"success": true, "path": "..."}`。

### 3.2 动态执行沙盒与上下文注入

服务端在隔离的执行作用域（`globals` 字典）中动态执行用户提交的代码，注入以下环境：
* `swApp`：已预连接且处于就绪状态的 `SldWorks.Application` COM 实例。
* `args`：由客户端传入的参数列表（`list[str]`）。
* `set_output(data: dict)`：辅助函数，供脚本输出键值对数据，最终在 JSON 响应的 `data` 字段中返回。
* `save_canvas(path: str = "canvas.png", doc = None)`：高阶辅助函数，直接将当前文档（或指定文档）的 3D 画布渲染保存为指定路径图片。AI 生成的脚本可直接单行调用看图。
* `to_win_path(path: str)` 与 `to_linux_path(path: str)`：内置路径双向解析函数。
* `log(msg)` 与 `log_err(msg)`：标准格式化日志工具。

### 3.3 Linux 守护进程管理工具 (`sw-daemon`)

管理守护进程与相关辅助服务的启停与健康状态：
* `sw-daemon start [options]`：
  * 检查并确保 Xvfb 显示环境（`:99`）正常就绪。
  * 若指定 `--vnc`，则拉起 `x11vnc`。**默认追加 `-viewonly` 参数（只看模式）**。
  * 若指定 `--vnc-interactive`，则不带 `-viewonly`，允许远程客户端发送鼠标键盘事件。
  * 在后台使用 Wine Windows Python 启动 `daemon_server.py`。
  * 循环轮询 `GET /v1/health` 最多 45 秒，直到返回 `ready: true`，并将 PID 写入 `/tmp/sw-daemon.pid`。
* `sw-daemon stop`：
  * 发送停止指令，通知 `swApp.ExitApp()` 并优雅终止 Wine 进程及关联的 VNC 进程。
* `sw-daemon restart`：
  * 安全停止后重新启动。
* `sw-daemon status`：
  * 检查 PID 与 HTTP 健康状态，输出当前进程状态与运行指标。

### 3.4 Linux 原生客户端工具 (`sw-cli`)

作为开发者、自动化工作流及 AI Agent 的核心调用入口：
* **脚本执行**：
  * `sw-cli run <script_path.py> [script_args...] [--timeout 60] [--json]`
  * 读取本地 Python 文件内容，将请求发送至 `127.0.0.1:18282/v1/execute`。
* **内联代码执行**：
  * `sw-cli eval "print(swApp.RevisionNumber())" [--json]`
* **3D 画布视图导出（AI 多模态首选）**：
  * `sw-cli canvas [output.png] [--json]`：调用 SolidWorks 原生光栅化渲染，导出当前活动 3D 模型的干净画布图像（无窗口边框、无菜单栏，纯几何）。
* **整机屏幕抓取（调试/冒烟测试）**：
  * `sw-cli screenshot [output.png]`：直接抓取 Display `:99` 的当前画面（含特征树与弹窗），保存为指定路径的 PNG 图像。
* **自愈与自动拉起**：
  * 若执行命令时检测到守护进程未运行，可提示或通过 `--auto-start` 选项在后台自动拉起 `sw-daemon` 后再行执行。

---

## 4. 容错防御与自愈机制

1. **用户脚本异常隔离**：
   - 脚本中的语法错误、运行期异常或 `sys.exit()` 调用均被捕获在沙盒内。
   - 发生错误时完整提取异常回溯（Traceback）填入 `stderr`，标记 `success: false`，服务端进程绝不退出。
2. **执行看门狗超时中断**：
   - 服务端启动后台守护定时器。若脚本执行时间超过请求指定的 `timeout`（默认 60s），立即触发中断并返回超时错误响应。
3. **COM 异常检测与自愈**：
   - 若检测到 `0x800706BA`（RPC 服务器不可用）或 `SLDWORKS.exe` 进程终止，守护进程标记 `sw_connected: false` 并尝试自动重建 COM 实例，避免服务陷入永久不可用。
4. **无头弹窗压制**：
   - 守护服务端强制保持 `UserControl = False`，并在启动时写入静默首选项，规避任何可能造成无头环境挂起的模态对话框。

---

## 5. 自动化测试与持续集成策略

遵循测试驱动开发（TDD）理念，全部测试用例均可在本地开发机或无 GPU/无真实 SW 授权的极简 CI 环境中运行：

1. **客户端测试 (`runtime/tests/test_cli_script.py`)**：
   - 测试 `sw-cli` 的命令行解析（`run`、`eval`、`status`、`screenshot`、`--json`）。
   - 通过本地 Mock HTTP Server 验证请求体的组装与对返回结果的格式化/退出码映射。
2. **守护脚本测试 (`runtime/tests/test_daemon_script.py`)**：
   - 测试 `sw-daemon` 的参数处理（`--vnc` 默认追加 `-viewonly`、`--vnc-interactive` 允许输入、`--port`、`--timeout`）。
   - 验证 PID 记录、状态检测及异常退出的容错逻辑。
3. **服务端沙盒测试 (`runtime/tests/test_daemon_server.py`)**：
   - 使用 Mock COM 对象测试 `daemon_server.py` 的执行沙盒：测试全局变量注入（`swApp`、`args`、`set_output`）、标准输出捕获及超时熔断。
4. **CI 冒烟测试与图像产物归档**：
   - 在 CI 流程中执行真实或 Mock 冒烟测试：启动 `sw-daemon --vnc`，执行测试脚本，并调用 `sw-cli screenshot smoke_result.png`。
   - 将 `smoke_result.png` 声明为 GitLab CI / GitHub Actions 的 `artifacts`，便于通过 Web 界面直观复核运行状态。

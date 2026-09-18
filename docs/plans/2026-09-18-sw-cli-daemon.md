# DockerSW CLI 与常驻 Daemon 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 subagent-driven-development（推荐）或 executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在 DockerSW 中构建常驻守护进程（`sw-daemon`）与 CLI 交互入口（`sw-cli`），支持 Python 脚本动态执行、`swApp` 上下文自动注入、结构化 `--json` 响应、VNC 监看（默认只看 `-viewonly`）以及冒烟测试屏幕捕获。

**架构：** 在 Wine Windows Python 环境内常驻轻量 HTTP 服务（`daemon_server.py`，绑定 `127.0.0.1:18282`），持有单例 `SldWorks.Application`；Linux 容器端提供 `sw-daemon` 守护生命周期管理脚本与 `sw-cli` 原生客户端命令，实现毫秒级响应、异常沙盒隔离与 CI 产物图像捕获。

**技术栈：** Python 3 (win32com / pythoncom / http.server / unittest), Bash, Wine 11.x, Xvfb, x11vnc, Openbox

**规格：** [docs/specs/2026-09-18-sw-cli-daemon-design.md](file:///Volumes/Data/Workspace/DockerSWPreinstalled/docs/specs/2026-09-18-sw-cli-daemon-design.md)

## 全局约束

- 守护服务端仅监听 `127.0.0.1:18282` 本地回环，禁止外部非授权暴露。
- 脚本执行沙盒必须捕获语法错误与运行时异常，杜绝服务端进程崩溃，错误以 `success: false` 与 `stderr` 形式结构化返回。
- 必须支持看门狗超时中断，默认超时 60s。
- `sw-daemon --vnc` 默认开启 `-viewonly`（只看模式），只有显式指定 `--vnc-interactive` 时才允许鼠标键盘交互。
- `sw-cli` 输出必须双模对齐：默认直接打印 stdout/stderr 且退出码透传；`--json` 时输出单行或标准 JSON 对象。
- 所有单元测试必须能脱离真实 GPU 和真实 SolidWorks 授权在纯离线 Mock 环境下运行通过。

---

### 任务 1：实现 Wine 端常驻服务与沙盒引擎 (`daemon_server.py`) (TDD)

**文件：**
- 创建：`runtime/tests/test_daemon_server.py`
- 创建：`runtime/scripts/daemon_server.py`

- [ ] **步骤 1：编写失败的单元测试**

编写测试用例覆盖：
1. 请求处理类 `DaemonRequestHandler` 的路由分发与上下文构建。
2. 沙盒执行函数 `execute_code_snippet`：
   - 注入变量测试：验证 `swApp`、`args`、`set_output`、`save_canvas`、`to_win_path`、`to_linux_path` 在代码内可用。
   - 标准输出与错误捕获测试：验证 `print()` 输出写入 `stdout`。
   - 异常捕获测试：验证未捕获异常返回 `success: False` 并携带 traceback。
   - 超时机制测试：验证看门狗机制能够截断超时任务。
3. `GET /v1/health` 路由响应结构。
4. `POST /v1/canvas` 路由响应结构（调用 `SaveAs3` 导出 3D 纯净模型视图 PNG）。

- [ ] **步骤 2：运行测试验证失败**

运行：`python3 -m unittest runtime/tests/test_daemon_server.py -v`  
预期：FAIL，报错 `ModuleNotFoundError` 或文件不存在。

- [ ] **步骤 3：实现 `runtime/scripts/daemon_server.py` 服务端**

实现包含：
1. 模块导入兼容：在 Linux 离线单测与 Wine Windows 环境下优雅适配（延迟或可选导入 `pythoncom` / `win32com`，提供 Mock 注入支持）。
2. `execute_code_snippet(code, args, timeout, sw_app)` 执行沙盒，内置 `save_canvas` 高阶辅助函数。
3. `DaemonServer` 与 `DaemonRequestHandler`（处理 `/v1/health`、`/v1/execute`、`/v1/canvas` 与 `/v1/screenshot`）。
4. 路径映射工具 `to_win_path` 与 `to_linux_path`。

- [ ] **步骤 4：运行测试验证通过**

运行：`python3 -m unittest runtime/tests/test_daemon_server.py -v`  
预期：PASS（所有测试通过）。

- [ ] **步骤 5：Commit**

```bash
git add runtime/tests/test_daemon_server.py runtime/scripts/daemon_server.py
git commit -m "feat(daemon): implement Wine daemon server with sandbox and canvas export"
```

---

### 任务 2：实现 Linux 守护进程管理工具 (`sw-daemon`) (TDD)

**文件：**
- 创建：`runtime/tests/test_daemon_script.py`
- 创建：`runtime/scripts/sw-daemon`

- [ ] **步骤 1：编写失败的单元测试**

编写测试用例覆盖：
1. 语法检查：`bash -n runtime/scripts/sw-daemon`。
2. 帮助输出：`sw-daemon --help` 验证包含 `start`, `stop`, `restart`, `status`, `--vnc`, `--vnc-interactive`, `--port`。
3. VNC 参数逻辑：
   - `--vnc` 启动时必须包含 `-viewonly` 参数。
   - `--vnc-interactive` 启动时不包含 `-viewonly` 参数。
4. 状态检查与 PID 探测：无 PID 文件或进程未存活时的退出状态。

- [ ] **步骤 2：运行测试验证失败**

运行：`python3 -m unittest runtime/tests/test_daemon_script.py -v`  
预期：FAIL，报错脚本不存在。

- [ ] **步骤 3：实现 `runtime/scripts/sw-daemon` 脚本**

实现包含：
1. 环境变量与命令解析（`start`, `stop`, `restart`, `status`）。
2. Xvfb 显示环境检测与准备（自动调用或确认 `:99`）。
3. VNC 控制集成：调用 `x11vnc`，严格遵守默认 `-viewonly` 策略，交互模式下放开。
4. Wine 后台拉起 `daemon_server.py`，并将 PID 保存至 `/tmp/sw-daemon.pid`。
5. 轮询 `/v1/health` 等待就绪（最长 45s 超时）。
6. `stop` 指令优雅终止服务与 Wine/VNC 相关进程。
7. 设置文件可执行权限：`chmod +x runtime/scripts/sw-daemon`。

- [ ] **步骤 4：运行测试验证通过**

运行：`python3 -m unittest runtime/tests/test_daemon_script.py -v`  
预期：PASS。

- [ ] **步骤 5：Commit**

```bash
git add runtime/tests/test_daemon_script.py runtime/scripts/sw-daemon
git commit -m "feat(daemon): add sw-daemon process manager with view-only VNC support"
```

---

### 任务 3：实现一等公民客户端 (`sw-cli`) 与屏幕捕获 (TDD)

**文件：**
- 创建：`runtime/tests/test_cli_script.py`
- 创建：`runtime/scripts/sw-cli`

- [ ] **步骤 1：编写失败的单元测试**

编写测试用例覆盖：
1. 语法检查：`bash -n runtime/scripts/sw-cli`。
2. 帮助信息：`sw-cli --help` 覆盖 `run`, `eval`, `status`, `canvas`, `screenshot`, `--json`, `--timeout`。
3. 子命令解析与请求分发：
   - `eval` 模式拼接 JSON 请求体。
   - `run` 模式读取 Python 文件并传递参数。
   - `canvas` 模式触发 3D 画布导出（向 `/v1/canvas` 发送请求）。
   - `screenshot` 模式触发 X11 整机桌面屏幕抓取。
4. `--json` 格式化：验证 AI 模式下输出纯 JSON，人类模式下输出纯 stdout/stderr 并保留退出码。

- [ ] **步骤 2：运行测试验证失败**

运行：`python3 -m unittest runtime/tests/test_cli_script.py -v`  
预期：FAIL，报错脚本不存在。

- [ ] **步骤 3：实现 `runtime/scripts/sw-cli` 脚本**

实现包含：
1. 参数解析系统（支持 `run`, `eval`, `status`, `canvas`, `screenshot` 及全局选项 `--json`, `--timeout`, `--host`, `--port`）。
2. HTTP 通信封装（基于 `curl` 或 Python 标准库 `urllib`）。
3. 状态码与响应解析：根据 `--json` 标志切换纯文本终端展示或 JSON 原始输出，退出码与服务返回对齐。
4. 3D 画布导出逻辑（`canvas`）：调用守护服务 `/v1/canvas` 渲染当前活动文档的 3D 模型纯净视口。
5. 屏幕截取逻辑（`screenshot`）：直接通过 X11 工具（如 `import`、`xwd` 或 Wine 屏幕服务）抓取 `:99` 显示器保存为 PNG。
6. 设置文件可执行权限：`chmod +x runtime/scripts/sw-cli`。

- [ ] **步骤 4：运行测试验证通过**

运行：`python3 -m unittest runtime/tests/test_cli_script.py -v`  
预期：PASS。

- [ ] **步骤 5：Commit**

```bash
git add runtime/tests/test_cli_script.py runtime/scripts/sw-cli
git commit -m "feat(cli): add sw-cli client with run, eval, canvas, and screenshot commands"
```

---

### 任务 4：容器系统集成与文档更新

**文件：**
- 修改：`runtime/Dockerfile`
- 修改：`README.md`
- 修改：`docs/dockersw-headless-design.md`

- [ ] **步骤 1：在 `runtime/Dockerfile` 中安装与链接新命令**

在 `Dockerfile` 中将 `sw-daemon` 与 `sw-cli` 复制/链接到 `/usr/local/bin/`，确保容器内任意终端可直接执行。

- [ ] **步骤 2：更新 `README.md` 与设计文档**

1. 在 `README.md` 中新增「常驻 Daemon 与 CLI 交互」章节，展示：
   - `sw-daemon start --vnc` 启动方式（强调默认 view-only 监看）。
   - `sw-cli run`、`sw-cli eval` 以及 `sw-cli screenshot` 用法示例。
   - `--json` 针对 AI Agent 的接入指引。
2. 在 `docs/dockersw-headless-design.md` 中更新系统架构拓扑。

- [ ] **步骤 3：运行全量单元测试套件**

运行：`python3 -m unittest discover -s runtime/tests -v`  
预期：所有测试（历史 22 个 + 新增测试）全部 PASS。

- [ ] **步骤 4：Commit**

```bash
git add runtime/Dockerfile README.md docs/dockersw-headless-design.md
git commit -m "docs(runtime): integrate sw-cli and sw-daemon into image and docs"
```

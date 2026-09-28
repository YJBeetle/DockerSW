# Wine 下的 SOLIDWORKS 交互界面兼容修复

DockerSW 的主要用途是无头 CI，但在启用 VNC 后也应尽量保留可用的
SOLIDWORKS 图形界面。这里记录只影响 Wine 窗口行为、不属于 SWCLI 协议层的修复。

## PropertyManager 确认与取消按钮

SOLIDWORKS 的 PropertyManager 会对同一个窗口重复调用 `SetCapture`。Windows 在捕获
窗口没有变化时不会向该窗口重发 `WM_CAPTURECHANGED`；Wine 11.16 默认仍会发送，
使左侧面板顶部的确认、取消等按钮错误地释放鼠标捕获。

`0003-win32u-no-capture-resend.patch` 为 Wine 增加
`WINE_NOCAPTURERESEND` AppCompat 标志。DockerSW 只为 `sldworks.exe` 写入该标志，
其他 Windows 程序保持 Wine 原始行为。该补丁与 OpenGL 修复一起在构建阶段进入
配对的 `ntdll.so` / `win32u.so`，运行时不改写二进制。

## PropertyManager 分组标题与下拉框

SOLIDWORKS 会对 PropertyManager 内部的真实子窗口请求 `HWND_TOPMOST` 或
`HWND_NOTOPMOST`。Windows 忽略这类子窗口的置顶层级变化；Wine 11.16 继续处理后，
面板分组标题会在反复布局中逐渐被挤压，最终文字宽度接近零。

`0005-win32u-ignore-child-topmost.patch` 对具有非桌面父窗口的纯 `WS_CHILD`
恢复 Windows 行为。补丁特意保留以下边界：

- `SWP_NOZORDER` 不受影响；
- 桌面父窗口不受影响，因此 Windows 下拉框使用的 `ComboLBox` 仍能移动和显示；
- `WS_POPUP` 窗口不受影响。

## GLX 前缓冲内容丢失（对应 MacSW 0004）

SOLIDWORKS 会使用 OpenGL 前缓冲绘制选择、预选和部分局部界面。在 Wine
11.16 的 X11/EGL 后端中，前缓冲会映射到后缓冲并通过强制交换模拟。连续两次
点击视口空白区域时，第二次交换可能显示尚未完整绘制的后缓冲，画面中实体消失，
但独立绘制的阴影仍然存在；旋转或悬停触发完整重绘后实体会再次出现。

MacSW 的 `0004-winemac-preserve-front-buffer-flush.patch` 修正的是 macOS
驱动中的额外缓冲交换。DockerSW 使用 X11 驱动，不能直接套用该源码补丁。
DockerSW 在 `headless_tweaks.reg` 中仅为 `SLDWORKS.exe` 设置
`X11 Driver\\UseEGL=N`，使用原生支持前缓冲绘制的 GLX 后端。其他 Wine
程序仍使用默认 EGL 后端。

仅切换到 GLX 仍有两个问题。Wine 采用 GLX 返回的第一个兼容像素格式，但 Xvfb
可能先返回 swap method 未定义的配置；此时第二次点击空白处仍会把未保留的后缓冲
显示出来。即使选择了 `GLX_SWAP_COPY_OML`，Space 视图选择器等短暂前缓冲内容在
VNC 中仍可能只显示为黑块，因为 Wine 对 on-screen surface 没有执行完成与 X11
flush。

`0004-winex11-flush-front-buffer.patch` 因此包含两项 X11 源码修复：

- 枚举 on-screen pixel format 时优先提供原生 `GLX_SWAP_COPY_OML` 配置；
- 提交前缓冲内容时对 on-screen 与 offscreen surface 都执行 `glFinish` 和 `XFlush`。

由于 `winex11.so`、`opengl32.so`、`win32u.so` 和 `ntdll.so` 使用 Wine 私有 ABI，
四个模块从同一份源码、同一个配置与同一次构建中产生，并作为整体安装。

在相同镜像、同一模型和相同操作下验证：EGL 第一次点击清除选择，第二次点击后
只剩阴影；仅优先 swap-copy 后模型不再消失，但 Space 选择器仍是黑块；加入显式
flush 后，模型、视图选择器及透明基准面均能显示。这里与 MacSW 保留相同的问题
编号 `0004`，但实现位于 `winex11.drv`。

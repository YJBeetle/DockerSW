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

## 模型在第二次点击空白处后消失（对应 MacSW 0004）

SOLIDWORKS 会使用 OpenGL 前缓冲绘制选择、预选和部分局部界面。在 Wine
11.16 的 X11/EGL 后端中，前缓冲会映射到后缓冲并通过强制交换模拟。连续两次
点击视口空白区域时，第二次交换可能显示尚未完整绘制的后缓冲，画面中实体消失，
但独立绘制的阴影仍然存在；旋转或悬停触发完整重绘后实体会再次出现。

MacSW 的 `0004-winemac-preserve-front-buffer-flush.patch` 修正的是 macOS
驱动中的额外缓冲交换。DockerSW 使用 X11 驱动，不能直接套用该源码补丁。
DockerSW 在 `headless_tweaks.reg` 中仅为 `SLDWORKS.exe` 设置
`X11 Driver\\UseEGL=N`，使用原生支持前缓冲绘制的 GLX 后端。其他 Wine
程序仍使用默认 EGL 后端。

在相同镜像、同一模型和相同操作下验证：EGL 第一次点击清除选择，第二次点击后
只剩阴影；GLX 连续点击后实体保持显示。这里与 MacSW 保留相同的问题编号
`0004`，但由于平台驱动不同，DockerSW 的实现是应用级运行时设置，而不是
`winemac.drv` 源码补丁。

# Wine 下的 SOLIDWORKS 交互界面兼容修复

DockerSW 的主要用途是无头 CI，但在启用 VNC 后也应尽量保留可用的
SOLIDWORKS 图形界面。这里记录只影响 Wine 窗口行为、不属于 SWCLI 协议层的修复。

## PropertyManager 确认与取消按钮

SOLIDWORKS 的 PropertyManager 会对同一个窗口重复调用 `SetCapture`。Windows 在捕获
窗口没有变化时不会向该窗口重发 `WM_CAPTURECHANGED`；Wine 11.16 默认仍会发送，
使左侧面板顶部的确认、取消等按钮错误地释放鼠标捕获。

`0002-win32u-no-capture-resend.patch` 为 Wine 增加
`WINE_NOCAPTURERESEND` AppCompat 标志。DockerSW 只为 `sldworks.exe` 写入该标志，
其他 Windows 程序保持 Wine 原始行为。该补丁与 OpenGL 修复一起在构建阶段进入
配对的 `ntdll.so` / `win32u.so`，运行时不改写二进制。

## PropertyManager 分组标题与下拉框

SOLIDWORKS 会对 PropertyManager 内部的真实子窗口请求 `HWND_TOPMOST` 或
`HWND_NOTOPMOST`。Windows 忽略这类子窗口的置顶层级变化；Wine 11.16 继续处理后，
面板分组标题会在反复布局中逐渐被挤压，最终文字宽度接近零。

`0003-win32u-ignore-child-topmost.patch` 对具有非桌面父窗口的纯 `WS_CHILD`
恢复 Windows 行为。补丁特意保留以下边界：

- `SWP_NOZORDER` 不受影响；
- 桌面父窗口不受影响，因此 Windows 下拉框使用的 `ComboLBox` 仍能移动和显示；
- `WS_POPUP` 窗口不受影响。

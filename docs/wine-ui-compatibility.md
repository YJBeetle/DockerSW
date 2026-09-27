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

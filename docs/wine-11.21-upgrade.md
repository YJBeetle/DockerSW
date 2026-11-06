# Wine 11.21 升级

运行时版本统一由 `runtime/managed_com.env` 提供：Wine 源码 11.21、WineHQ
Jammy DEB `11.21~jammy-1`。源码归档使用 SHA-256 校验；Wine-Mono 保持 11.3.0。
构建工具只存在于独立 builder 阶段。

## 补丁处理

| 编号 | 11.21 中的处理 |
| --- | --- |
| 0000 | 迁移到新的通用 FBO 实现，保留 24/32 位 DIB 转换；使用 32 位暂存表面处理行填充和上下方向，同时保留 Linux 传统像素传输路径 |
| 0003 | 更新鼠标捕获修复的源码上下文，仍仅由 SOLIDWORKS 兼容开关启用 |
| 0004 | 保留 Linux GLX 前缓冲修复 |
| 0005 | 更新子窗口置顶修复的源码上下文 |
| 0007 | 保留 SOLIDWORKS 专用的 COM 注册等待，默认 300 秒；其他 COM 类保持 30 秒 |
| 0010 | 保留树形控件图标间距修复 |
| 0011 | 删除；上游 `c4e6fd93765e652e7b3f4cecbc13198f9582fd6e` 已实现 PrintWindow 表面复制，同时删除旧兼容开关 |
| 0012 | 保留自定义字体回退链 |
| 0014 | 保留 MSXML SchemaCache 命名空间修复 |
| 0020 | 保留 MSXML 空命名空间序列化修复 |

未引入 MacSW 的 macOS / Rosetta 专用补丁。

## 验证边界

所有保留补丁均在 Wine 11.21 原始源码上通过应用检查。0000 的专项 C 测试
覆盖 24/32 位、正负高度、奇数宽度行填充、像素传输状态恢复和转换失败；该测试
使用模拟 GL 与转换器，不能代替真实 Wine / SOLIDWORKS 验收。

镜像构建继续执行 MSXML 与字体回退原生探针；交付工作流继续执行轻量可见与
完整隐藏测试。升级的编译、真实运行和镜像晋升结果应以对应工作流为准。

## workspaceroot 原生复验

使用 CI 候选 `ghcr.io/yjbeetle/sw-runtime:sha-de3a1cd`，镜像摘要
`sha256:800c2745d25fd890fbff62e6068ef258c90d8ce8759ebb394e5c365769bd0772`。
已核对 Wine 为 11.21、四个 WineHQ 包均为 `11.21~jammy-1`，成品中没有
编译器、`/build/source` 或 `/build/obj`。

- 7 个模块在 workspaceroot 实编译成功。
- 真实 Win32/WGL/GDI 像素探针：8/8 通过，退出 0；覆盖 24/32 位、7/8 宽度、
  正负高度、非对称初始上传、逐像素回读、行方向、pack 状态、FBO 绑定和双 context。
  使用 Wine 11.21 / Mesa llvmpipe；legacy 非 FBO、MSAA、Alpha 未纳入本次真实探针。
- MSXML：8 个用例，failures=0，退出 0。
- 字体回退：936→1252 码页切换的四阶段分别 14/22/3/5 项检查，全部零失败，退出 0。

临时探针容器均已清理。远端日志保留于 `/tmp`：
`dockersw-bitmap-enhanced1121-final.log`、`dockersw-wine1121-msxml-rerun.log`、
`dockersw-wine1121-fontlink-rerun.log`。像素日志 SHA-256 为
`d1d11df42ff5d0121bdca0084ef54eb99e97b059dd9d9e39de5564613a1e85af`。

完整交付验证见 [升级工作流](https://github.com/YJBeetle/DockerSW/actions/runs/42248079598)。

## 完整镜像交付结果

工作流 `42248079598`（源码 `de3a1cd`）两个作业均成功：

- 6 个真实 STEP/PDF/DWG 导出产物校验通过。
- 19 组隔离功能测试全部通过，包括装配体、图纸原位保存/另存为和 Toolbox。
- 本地化镜像与轻量可见流程通过。
- `2025` 系列镜像晋升成功；远端查询确认 `2025-zh-cn-cli` 与
  `sha-de3a1cd-zh-cn-cli` 的 manifest 相同，对应镜像摘要
  `sha256:e7df83dfafcf9222ad3053e46720b771a96995c9e0b348d71d8fa99028b45b1d`。

此处晋升范围为 `2025` 分支；`latest` 系列由 `main` 的工作流维护。

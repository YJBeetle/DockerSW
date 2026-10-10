# Wine-Mono CCW 兼容修复与共享运行时

## 现象和证据边界

DockerSW 的某些工程图导出／清理路径曾触发 `cominterop.c` 的
`ccw->ref_count > 0` 断言，导致 SOLIDWORKS 退出，后续 COM 请求报告
`RPC server unavailable`。MacSW 的 Toolbox 新规格确认也触发相同断言。

最小探针在托管对象仍然存活时，将 CCW 计数释放到零，再多调用两次
`Release`，随后重新 `AddRef` 和 `Release`。Windows .NET Framework x86/x64
返回 `-1` 并允许重新获取引用；原 Wine-Mono 在第一次多余 Release 断言退出。
这不是对已被 GC 回收的对象调用 COM 的安全性保证，也不证明全部并发 GC 场景。

## 当前方案

DockerSW 与 MacSW 使用同一个
[共享 CCWFix 版本](https://github.com/YJBeetle/wine-mono/releases/tag/wine-mono-11.3.0-X86StdcallFix-ComRegistration-CCWFix)，
保留已有 v3 的 x86 stdcall 与托管 COM 注册修复。源码身份：

- Wine-Mono 集成：`eb8d3270298d2d59f7e304d23e6af0ff374f4559`。
- Mono 引擎：`edc3bfecdcb5c1c4705bdc9b82257d1d35143f06`。

[源码修复](https://github.com/YJBeetle/mono/commit/edc3bfecdcb5c1c4705bdc9b82257d1d35143f06)
在零计数时返回 `-1`，但内部计数保持零；正常递减使用原子 CAS，保留 1→0
时从强 GC 句柄切换到弱句柄的原有逻辑。不通过永久 AddRef 或关闭 GC 保活。

原二进制 NOP 方案只跳过断言，仍将内部计数减到负数，不等价于这一行为。
现已移除 `patch_wine_mono.pl` 及构建、安装、入口点中的调用，不再扫描或改写 DLL。
脚本及旧单测可从 Git 历史恢复。

`runtime/managed_com.env` 锁定共享 Release、源码提交及全部运行文件的 SHA256。
`fetch_managed_com.sh` 下载同一共享版本的双架构 DLL、mscorlib 和 RegAsm；
`prepare_managed_com.sh` 在复制前后校验，覆盖全新及挂载的已有 prefix。
共享源码归档地址和哈希写入镜像内 `managed-com/SOURCE.txt`，无需项目本地构建 Mono。
原有 BTLS DLL 和 `System.dll` 不改动；x86 保持 v3 的 BTLS-disabled 配置，
x86 BTLS 调查另行进行。

## 回归和验收

共享发布已通过同一源码提交的
[双架构 Wine 门禁](https://github.com/YJBeetle/wine-mono/actions/runs/38078186166)、
[Windows CLR 对照](https://github.com/YJBeetle/wine-mono/actions/runs/38078186208) 和
[COM 注册集成](https://github.com/YJBeetle/wine-mono/actions/runs/38078186212)。
CCW 门禁覆盖 x86/x64、JIT/解释器以及原引擎的预期失败对照。

DockerSW 镜像构建增加 `verify_mono_ccw.sh`，使用实际安装的运行时编译并执行
相同的七项 CCW 检查，分别运行 x86/x64、JIT/解释器。必须同时满足退出码零、
准确的完成标记、七项输出且无断言／异常；退出码零本身不算通过。
探针仅通过 BuildKit 绑定挂载，不进入最终镜像，也不在容器日常启动时执行。

本地离线单测验证共享版本锁定、复制前后校验、损坏输入拒绝、幂等复制以及
完成标记的成功／失败判定；不是 Linux 镜像构建或 SOLIDWORKS 导出实测。
真实 Linux 容器中的运行时门禁、Toolbox 及 DWG／PDF 导出仍由 DockerSW CI
在新镜像上验证，不能用共享最小探针替代完整 CAD 验收。

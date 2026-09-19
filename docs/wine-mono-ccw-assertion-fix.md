# Wine-Mono CCW 引用计数断言缺陷与修补技术文档

本文档记录了在 Linux 无头容器（Wine 11.x + Wine-Mono 11.3.0）环境下，SOLIDWORKS 导出工程图为 DWG 等依赖托管 COM (.NET) 的格式时，偶发出现 `* Assertion at .../cominterop.c:3392, condition 'ccw->ref_count > 0' not met` 导致 `SLDWORKS.exe` 进程闪退及后续所有导出任务发生 `RPC server unavailable` 的根本原因、逆向分析、热补丁方案与设计实现。

---

## 1. 现象与排查背景

在 GitLab CI 等高并发批处理场景下，使用 `sw-cli document export` 连续导出多个复杂工程图（`.SLDDRW` -> `.PDF` 与 `.DWG`）时：
1. **PDF 导出成功**：在第一阶段通常能顺利导出高质量 PDF；
2. **DWG 转换时偶发崩溃**：当进入 DWG 转换环节，控制台输出断言失败：
   ```text
   * Assertion at /builds/mono/wine-mono/wine-mono-11.3.0/mono/mono/metadata/cominterop.c:3392, condition `ccw->ref_count > 0' not met
   AttributeError: <unknown>.Extension
   pywintypes.com_error: (-2147023174, 'RPC server unavailable.', None, None)
   ```
3. **雪崩式连锁失败**：由于该断言直接调用了 `abort()` 触发 `SIGABRT`，宿主 `SLDWORKS.exe` 进程瞬间暴毙退出。如果导出脚本未作单条目进程级隔离，后续所有排队导出的模型条目均会因 COM 连接中断而全军覆没。

---

## 2. 源码级根本原因分析 (Root Cause)

SOLIDWORKS 的工程图转换组件包含混合架构，DWG/DXF 导出插件内部通过 COM 互操作（COM Interop）调用托管 .NET 运行时组件。

在 Mono / Wine-Mono 的内部实现中，当原生 COM 宿主持有托管对象接口时，Mono 会为其分配一个 **CCW (COM Callable Wrapper)**，其引用计数保存在 `ccw->ref_count`。

### 缺陷：Mono 对外部 COM 调用的硬断言过严

在 Wine-Mono 源码 `mono/mono/metadata/cominterop.c` 的 `cominterop_ccw_release` 函数中：
```c
/* Wine-Mono cominterop.c */
static ULONG STDMETHODCALLTYPE
cominterop_ccw_release (IUnknown *pUnk)
{
    MonoCCW *ccw = ...;
    ...
    g_assert (ccw->ref_count > 0); /* <-- 崩溃根因：第 3392 行硬断言 */

    if (InterlockedDecrement (&ccw->ref_count) == 0) {
        mono_ccw_destroy (ccw);
        return 0;
    }
    return ccw->ref_count;
}
```

- **语义差异**：
  - **Windows 原生 .NET CLR**：设计为宽容防御模式。当面对某些第三方复杂 COM 组件（或多线程并发释放回调）偶发多调用了一次 `Release()`（Double-Release）时，CLR 会容错忽略，绝不会因为外部 COM 宿主的计数瑕疵直接调用 `abort()` 杀死调用方进程。
  - **Wine-Mono**：此处误用了不可关闭的 `g_assert`。当 `ccw->ref_count` 已经是 0 时，一旦再次收到 Release，断言失败立即触发 `abort()`，直接杀死 `SLDWORKS.exe` 宿主！

---

## 3. 逆向定位与汇编热修补方案

为了在无需重新完整构建庞大 Wine-Mono 编译链的前提下实现即时免疫，我们在 64 位核心动态链接库 `libmono-2.0-x86_64.dll` 上进行了指令级逆向分析与热修补。

### 3.1 指令级定位 (x86_64)

在 `libmono-2.0-x86_64.dll`（PE 映像基址 `0x180000000`）中，`cominterop_ccw_release` 汇编如下：

```assembly
; 文件偏移 0x175588 / 内存 RVA 0x176188
180176188: 4d 8b 6e 08           movq   0x8(%r14), %r13       ; %r13 = ccw
18017618c: 4d 85 ed              testq  %r13, %r13            ; ccw 是否为 NULL
18017618f: 0f 84 9f 00 00 00     je     0x180176234           ; 若 NULL 跳转断言 0xd3f
180176195: 41 83 7d 00 00        cmpl   $0x0, (%r13)          ; 比较 ccw->ref_count 与 0
18017619a: 0f 84 ac 00 00 00     je     0x18017624c           ; 【关键分支】若 == 0，跳转调用 mono_assertion_message(0xd40) abort()!
1801761a0: 48 8b 80 48 04 00 00  movq   0x448(%rax), %rax
...
1801761ad: bd ff ff ff ff        movl   $0xffffffff, %ebp     ; %ebp = -1
1801761b2: f0 41 0f c1 6d 00     lock xaddl %ebp, (%r13)      ; 原子减 1 并返回旧值
1801761b8: ff cd                 decl   %ebp                  ; 计算新引用计数
1801761ba: 74 44                 je     0x180176200           ; 只有新计数刚好为 0 时才跳转销毁 CCW
...
1801761ed: 89 e8                 movl   %ebp, %eax            ; 返回引用计数
1801761ff: c3                    retq
```

### 3.2 补丁设计与数学安全性

我们将 `0x18017619a` 处长度为 6 字节的跳转断言指令：
```
原机器码：0f 84 ac 00 00 00  (je 0x18017624c)
```
替换为 6 个等长的单字节 NOP 指令：
```
补丁机器码：90 90 90 90 90 90  (6 * nop)
```

**为什么这种替换是 100% 安全且不会发生二次析构的？**
1. **彻底免疫 abort**：断言分支不再触发，宿主进程绝不崩溃；
2. **防重释放析构保证**：
   - 当原计数为 $1$（正常释放）时：`lock xaddl` 减完为 $0$，`decl` 后 `%ebp == 0`，触发 `je 0x180176200` 正确执行 CCW 销毁逻辑。
   - 当原计数为 $0$（Double-Release 异常）时：`lock xaddl` 减完变为 $-1$，`decl` 后 `%ebp == -2`，条件不成立，**绝不会跳转到销毁分支**！
3. **干净安全返回**：函数平稳完成 GC 状态恢复并返回，调用方获得非零返回值，行为对齐微软原生 .NET CLR。

---

## 4. 工程化集成与四重保障架构

在 `DockerSW` 体系中，通过如下四个层面全生命周期自动应用与校验补丁：

1. **补丁脚本**：[docker/patch_wine_mono.pl](file:///Volumes/Data/Workspace/DockerSWPreinstalled/DockerSW/docker/patch_wine_mono.pl)
   - 包含快速偏移（`0x175588`）与全局哈希扫描双模式；
   - 具备完整幂等性（重复执行不报错且安全跳过）。
2. **基础镜像构建期应用**：[docker/init_wineprefix.sh](file:///Volumes/Data/Workspace/DockerSWPreinstalled/DockerSW/docker/init_wineprefix.sh)
   - 在基础镜像首次装载 Mono 运行时即刻固化补丁。
3. **预安装镜像构建期应用**：[scripts/sw-install](file:///Volumes/Data/Workspace/DockerSWPreinstalled/DockerSW/scripts/sw-install)
   - 在 SolidWorks 安装及前置环境准备后执行自动校验。
4. **容器运行期 Entrypoint 防护**：[docker/entrypoint.sh](file:///Volumes/Data/Workspace/DockerSWPreinstalled/DockerSW/docker/entrypoint.sh)
   - 即使使用者挂载了外部私有 WinePrefix 或外部 Mono 目录，每次容器启动都会自动识别并应用修补。
5. **自动化单元测试覆盖**：[tests/test_patch_wine_mono.py](file:///Volumes/Data/Workspace/DockerSWPreinstalled/DockerSW/tests/test_patch_wine_mono.py)
   - 包含快路径、全盘扫描、幂等性及真实 DLL 文件的完整单元测试。

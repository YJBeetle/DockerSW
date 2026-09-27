# Wine 11.x 24-bit DIB OpenGL 离屏渲染缺陷与修补技术文档

本文档记录了在 Linux 无头容器（Wine 11.x + Xvfb）环境下，SOLIDWORKS 导出包含 3D 着色视图（Shaded / Shaded with Edges）的工程图时出现“**水平 4 重平铺重复、斜向交替条纹网格、纵向 25% 截断**”的根本原因、源码修复及构建边界。

---

## 1. 现象与排查背景

在无头 CI 环境中使用 `sw-cli document export` 导出 SOLIDWORKS 官方图纸（如 `cabinet_bath.slddrw` 与 `bezel moldbase.slddrw`）为 PDF 时：
- **线框视图（Wireframe / HLR）**：导出完全正常且矢量线条清晰；
- **3D 着色视图（Shaded View）**：出现严重的几何畸变与光栅瑕疵：
  1. 水平方向被压缩为原本的 $1/4$，并连续横向**平铺复制了 4 次**；
  2. 整幅图像交替覆盖有规律的**斜向条纹扫描线与摩尔网格**；
  3. 视图顶部丢失约 **25% 的有效高度**（纵向比例失真）。

---

## 2. 源码级根本原因分析 (Root Cause)

SOLIDWORKS 在无头模式下渲染 3D 着色视图时，通过 Windows GDI 内存设备上下文（Memory DC）创建 DIBSection 离屏位图，并利用 OpenGL 扩展将该内存表面绑定为渲染目标。

在渲染完成并向 GDI 内存表面同步时，Wine 的底层显示驱动核心模块 **`dlls/win32u/opengl.c`** 中的 `flush_memory_dc` 承担了双向数据交换。Wine 原生代码如下：

```c
/* Wine dlls/win32u/opengl.c: flush_memory_dc */
static void flush_memory_dc( HDC hdc, struct opengl_context *context, BOOL write )
{
    ...
    int width = info->bmiHeader.biWidth, height = info->bmiHeader.biSizeImage / 4 / width;
    if (write) funcs->p_glDrawPixels( width, height, GL_BGRA, GL_UNSIGNED_BYTE, bits.ptr );
    else funcs->p_glReadPixels( 0, 0, width, height, GL_BGRA, GL_UNSIGNED_BYTE, bits.ptr );
    ...
}
```

该函数存在两处致命缺陷：

### 缺陷 1：强制写死 32bpp (`GL_BGRA`)，导致 4 重平铺与斜纹条纹

- **格式协商**：Wine 在 Xvfb 内存 DC 环境下枚举的 OpenGL 离屏像素格式（Pixel Format）默认色深为 24 位（`ColorBits = 24`，无 Alpha 通道）。SOLIDWORKS 据此分配了 24bpp（每像素 3 字节）的 GDI DIB 内存缓冲区，每行跨度（stride）为：
  $$\text{stride} = (\text{width} \times 3 + 3) \ \& \sim 3$$
- **驱动传参错误**：Wine 在调用 `glReadPixels` / `glDrawPixels` 时，**无条件硬编码传入了 `GL_BGRA`（每像素 4 字节）**。
- **步进错位**：Mesa/OpenGL 驱动按照 4 字节一个像素向内存写入，而 GDI DIB 缓冲区的行宽与像素跨度是按 3 字节组织的：
  - 步进比率恰好呈现 $4 : 1$：每写入一行，实际跨越了 4 倍于预期的内存宽度，使得水平图像在单行内折返平铺了 **4 个完整周期**；
  - 每一扫描行交替错位 1 个字节的色彩通道（B->G->R 循环移位），形成了极其均匀规律的**斜向交替扫描线条纹与彩色网格**。

### 缺陷 2：高度推算公式错误，导致 25% 纵向截断

- Wine 错误地假设所有图像都是 32bpp（4 字节/像素），使用如下公式反算高度：
  $$\text{height} = \frac{\text{biSizeImage}}{4 \times \text{width}}$$
- 但对于 24bpp 图像，$\text{biSizeImage} \approx \text{width} \times \text{height} \times 3$。
- 将其代入公式计算：
  $$\text{height}_{\text{actual}} = \frac{\text{width} \times \text{height} \times 3}{4 \times \text{width}} = \frac{3}{4} \times \text{height}$$
- 有效高度被直接砍去 $25\%$，导致导出的 3D 着色视图顶部严重截断。

---

## 3. 源码修复与构建实现

`runtime/wine-patches/0001-win32u-fix-24bit-memory-dc.patch` 直接修改
`flush_memory_dc`：

```c
int width = info->bmiHeader.biWidth, height = abs( info->bmiHeader.biHeight );
GLenum format = info->bmiHeader.biBitCount == 24 ? GL_BGR : GL_BGRA;
```

这样高度来自 DIB 自身，像素格式也与实际位深一致。补丁不再依赖编译器生成的固定指令、ELF 偏移或特征码。

构建阶段固定并验证 Wine 11.16 源码归档 SHA-256，在 Ubuntu 22.04 中应用补丁后只构建需要的 Unix 核心模块。`win32u.so` 链接并使用 `ntdll.so` 的 Wine 私有 ABI，因此两个模块必须来自同一份源码、同一个配置与同一次构建，并成对覆盖 WineHQ 包中的对应文件。只替换 `win32u.so` 即使版本号相同也不属于受支持的组合。

---

## 4. 架构设计与分层权责 (Separation of Concerns)

### 为什么应该“全部放在内层 (`DockerSW`)”？

在最初验证阶段，外层预安装仓库（`DockerSWPreinstalled`）的脚本曾临时增加过一行补丁调用。从软件工程和架构设计角度，该逻辑**应当 100% 收敛在内层 `DockerSW` 中**，外层不应感知任何 Wine 驱动层修补：

1. **出厂即固化（Build Time）**：
   `runtime/Dockerfile` 的独立构建阶段完成源码校验、补丁应用、编译与 strip；正式 `sw-runtime` 在首次运行 Wine 之前成对安装模块。
2. **运行期不可变（Run Time）**：
   entrypoint 与 `sw-install` 不再改写 Wine ELF。下游镜像天然继承已验证模块，运行期行为不会因文件权限或偏移变化而漂移。
3. **外层仓库保持纯粹**：
   `DockerSWPreinstalled` 的唯一定位是**“私有介质搬运工与安装启动器”**（挂载 ISO $\rightarrow$ 执行 `sw-install` $\rightarrow$ commit 镜像）。它不应该包含特定于底层 Wine 驱动的修补代码。

---

## 5. 验证与回归测试

1. **静态与构建测试**：`runtime/tests/test_wine_patches.py`
   - 验证源码版本与归档 SHA-256 固定；
   - 验证源码补丁在构建前先执行 dry-run；
   - 验证 `ntdll.so` 与 `win32u.so` 成对构建和安装；
   - 验证旧的运行期二进制改写器已移除。
2. **端到端 CI 冒烟测试**：
   - GitHub Actions [DockerSW Run 35029214287](https://github.com/YJBeetle/DockerSW/actions/runs/35029214287) 通过；
   - GitHub Actions [DockerSWPreinstalled Run 35029232045](https://github.com/YJBeetle/DockerSWPreinstalled/actions/runs/35029232045) 通过；
   - 实际导出的 `cabinet_bath.PDF` 与 `bezel moldbase.PDF` 经提取像素与渲染验证，条纹、4 重复制及截断现象彻底消除，画质高保真。

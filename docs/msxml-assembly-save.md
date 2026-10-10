# ASM 原生保存与 MSXML SchemaCache

移植自 MacSW `c1648c6b8bdb2a296abf8a4956de0626dccbbd10` 的源码补丁，
保留 `0014-msxml-schema-cache-namespace.patch` 编号与内容；七项原生探针来自
MacSW `45de3f9e5452b47d1e93d2374cc4d0f44d9fc489`。

SOLIDWORKS 将无 `targetNamespace` 的官方 `sw2005plusSchema.xsd` 放入非空
SchemaCache 命名空间。Wine 没有采用缓存的命名空间，导致装配体保存的 XML 验证
失败。MacSW 已通过捕获 XML/XSD 和 Windows MSXML6 对照定位此问题。
DockerSW 在 GitHub CI 与 workspaceroot 也观察到 ASM `SaveAs3` 返回错误码 1；
仅相同错误码不足以确定根因，必须使用 DockerSW 原生探针与保存重开对照验证。

补丁仅修改缓存的私有 DOM 副本，绑定无目标命名空间的 XSD 并调整必要的 QName。
保留已有命名空间、局部 form、XPath、调用者 DOM 和非法数据拒绝行为；不关闭验证，
不修改 SOLIDWORKS 或其官方 XSD。该修复独立于 Mono CCW 和 macOS 驱动。

## 构建与验证

MSXML6 的工厂转发到 Wine `msxml3` 实现，因此需要交付 `msxml3.dll`。
DockerSW 使用 `managed_com.env` 固定的 Wine 11.16 源码，与其他修复模块同阶段构建
x64 PE 模块，并在 wineboot 之前安装；初始化会将模板模块复制到 prefix 的 system32。
已有 SOLIDWORKS 进程必须正常退出后再使用新镜像，热替换文件不会更新已加载模块。

构建阶段编译跨平台探针，在实际运行时 prefix 中执行：退出码必须为 0、完成七项，
且出现独立行 `XML_NAMESPACE_PROBE_PASS`。失败或超时输出原始日志并阻止构建。
探针通过只读构建挂载运行，不进入成品镜像；编译器、源码及构建环境仍留在 builder。

共享 SWCLI modeling 门禁继续负责真实 ASM 的 SaveAs、原位 Save3、实际文件大小、
关闭重开、新文档 ID、配置与顶层特征树、只读重开后的 SHA-256 不变检查。
PRT 同样检查原位保存大小及重开几何。512 字节阈值只是截断保护，不能单独证明
模型正确。保存不是 Pack and Go，ASM 重开仍需访问原组件引用。

本次 Linux 实测结果待 workspaceroot 对照完成后记录；MacSW 证据不替代 DockerSW 验收。

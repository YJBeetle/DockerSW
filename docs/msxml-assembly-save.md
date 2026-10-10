# ASM 原生保存与 MSXML SchemaCache

移植自 MacSW `c1648c6b8bdb2a296abf8a4956de0626dccbbd10` 的源码补丁，
保留 `0014-msxml-schema-cache-namespace.patch` 编号与内容；七项原生探针来自
MacSW `45de3f9e5452b47d1e93d2374cc4d0f44d9fc489`。
探针仅将包含头改为 Ubuntu 22.04 MinGW 提供的 `msxml2.h`，仍通过明确的
MSXML6 ProgID 和接口 GUID 运行相同七项测试，不降级到 MSXML2。

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

## Linux 对照记录（2026-10-11）

workspaceroot 使用本项目的 Ubuntu 22.04 builder 编译模块，在已有
`sha-d1f1f9d-cli` 镜像上仅替换 `msxml3.dll`，并覆盖固定 SWCLI 源码进行独立实验。
这不是全量新镜像或正式流水线验收；MacSW 证据也不替代 DockerSW 验收。

- 原版模块七项探针有四项失败；替换模块后七项全部通过，非法整数仍被拒绝。
  探针在没有实际 X 服务的 `DISPLAY=:198` 下也可完成。
- 替换模块为 3,770,486 字节，SHA-256 为
  `d23b55698efc9b7f9f08b22cd936ce52e4d4ffcdd2bc8b4cf4e2bd8b795d0dc2`。
- 同一个隐藏宿主中，PRT 的 SaveAs、原位 Save3、关闭只读重开及几何/特征检查通过，
  保存文件为 80,824 字节，宿主 Windows PID 始终为 612，没有失败重试或宿主重启。
- 官方 `bezel moldbase.sldasm` 的 SaveAs 已返回 `api_saved=true`、`save_errors=0`，
  生成 1,121,483 字节文件；但随后 `GetSaveFlag=true`，SWCLI 正确返回
  `DocumentStillModified`。严格门禁因此没有继续原位 Save3 或重开，不能宣称 ASM
  完整闭环通过。MacSW 成功样本是空白/手工装配体，不是同一 bezel 门禁。
  独立只读打点确认 SaveAs 返回后已为 true，退出 `CommandInProgress` 作用域后仍为 true；
  父装配体及一个 ejector set 子装配体有修改标志，重建需求均为 0。
  未采集子装配体保存前状态，不能断言保存使它变脏，也不能排除请求作用域影响。
- 图纸只复制单个文件时，打开副本返回 `api_errors=2`，门禁正确拒绝。
  独立对照保留完整 Mold 树后，Save3、关闭只读重开、新 ID、顶层特征树与哈希检查通过，
  保存文件为 4,372,895 字节，三次打开错误/警告均为 0，37 个安装样本源文件哈希不变。
  因此正式宿主适配器须准备完整临时引用树，而不是放宽打开错误检查。

首个失败和原始日志保留在 workspaceroot 的
`/tmp/dockersw-msxml-proof-20261011.x9ocf3`；后续定位必须区分首次门禁结果与独立假设实验，
不能忽略修改状态、恢复重试或仅凭文件大小把失败改成成功。

补充验证边界：原 SaveAs 产物独立只读重开通过，配置和 25 个顶层特征签名保持一致，
文件 SHA-256 不变。该产物的独立副本在可写打开后 `modified=false`，原位 Save3、
关闭只读重开通过，保存文件为 1,123,238 字节，打开错误/警告均为 0；这不改判原始
SaveAs 严格门禁的失败。图纸最终隔离引用目录接线也通过，保存为 4,372,532 字节，
正式证据只包含图纸和结果记录，37 个安装源文件哈希保持不变。

原生 Windows 的 SWCLI CI #157、#158、#159 同样在官方 bezel 样例首次 SaveAs 后
返回 `DocumentStillModified`（原生保存成功、错误码 0、约 1.09 MB），不是 Wine 独有问题，
也不能仅凭该修改标志推断文件损坏。Windows 单元测试和 wheel 构建均通过。

## 自建装配体与正式保存检查

默认共享门禁通过 typed CLI 自建实体 PRT 和单零件 ASM，验证严格 SaveAs/Save3、
实际文件大小、关闭源 PRT 与 ASM 后的可写/只读重开、干净修改标志、配置/顶层特征树
和文件哈希。生成的 ASM 必须包含一个原生组件 `Reference`，其首次 SaveAs 也不允许
`DocumentStillModified`。这不是配合求解、嵌套装配或引用可移植性测试。

## 可选官方样例准备

显式传入 `--verify-sample-assembly-save` 时，共享门禁首先将官方样例另存为新的测试副本，
不对安装源文件执行原位保存。
只在首次样例准备阶段允许 `DocumentStillModified`，仍要求原生保存成功、错误码为 0、
采用正确目标路径、格式和实际文件大小有效；原始错误与修改标志记录在证据中。
其他错误不接受，也不改变 CLI 正式保存命令的严格行为。

准备后关闭并可写重开副本：必须是新文档 ID、打开错误/警告均为 0、`modified=false`，
配置和顶层特征树不变。随后原位 Save3 和关闭只读重开继续严格验证，第二次打开仍需
保存或保存后仍有修改均失败。这是明确的样例准备步骤，不是无限重试或清除 SaveFlag。

该准备流程已在 workspaceroot 的独立派生镜像中通过：首次 SaveAs 返回
`DocumentStillModified`，但原生错误码为 0、文件为 1,121,988 字节；关闭后可写重开
无修改，严格 Save3 后为 1,123,420 字节，再次只读重开配置与特征不变、哈希不变。
37 个安装样本源文件哈希不变，宿主 PID 616 未变；原始证据保存在
`/tmp/swcli-asm-stage1-20261011.Zn9G4t/evidence/modeling.json`。
这是样例准备流程的 Linux 独立实测，不替代新源码的完整镜像/Windows CI。

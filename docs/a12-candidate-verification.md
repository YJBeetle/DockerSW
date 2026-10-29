# SWCLI a12 开发候选验收（2026-10-30）

本候选固定 SWCLI `2cd569ccf99db6af0a5ef3cd07afa1c5b2d5d115`，版本为
`0.1.0a12.dev0`。Windows 和 Docker/Wine 完整验收均已完成并核对回执。
本记录不构成正式 a12 发布，也不构成 MacSW 验收。

## Windows 完整门禁

- 原 CI：[SWCLI #216 / 40926208032](https://github.com/YJBeetle/SWCLI/actions/runs/40926208032)。
- 双 Python 单测、wheel 构建及原生安装/建模/导出作业全部成功。
- 原生证据 artifact：`12924365824`，`swcli-windows-hosted-40926208032-1`。
- 原 ZIP SHA-256：`9e63b3bf755587761db2f0f3c33183279ffe6c38f1493e251846cc6653b4e848`，
  下载后与 GitHub artifact digest 核对一致。
- `swcli-native-smoke/hidden/runtime-sets/runtime-sets.json` 为
  `state=completed`、`success=true`、`suite=full`、`coverage_scope=full-plan`、
  `diagnostic_set=null`，19 组 / 20 个步骤全部通过。
- 各组 `cleanup_errors=[]`、`server_exit_code=0`，启动前和停止后的原生进程目录为空；
  实际 daemon 回执版本均为 `0.1.0a12.dev0`。
- 15 个成功导出回执均与归档实体大小一致，并检查文件头或容器结构：
  STEP 3 个，STL / 3MF / AMF / GLB / PDF / DWG 各 2 个。
  包含中文路径 STEP、第一角零件及第三角装配工程图 PDF / DWG。
- 外层 STEP 导出和 BMP 渲染也成功，实体分别为 16,068 和 1,440,054 字节。

## 公共贯穿切除

`reverse-cut/modeling/modeling.json` 的 `cases` 同时包含 `reverse-cut` 和
`through-all-cut`，`through_all_cases` 为圆 / 矩形 × front / top / right ×
normal / reverse 的全部 12 例；并非只运行 test-only 原生校准。

逐例独立复核归档回执及实体，确认：

- 由安装后的 CLI 经 endpoint/session 调用公共 `feature.cut-extrude --through-all`；
  原生端条件为 1，公共深度与深度公差均为 null，选体范围关闭，后台文档操作保留前台。
- 12 次对贯穿特征的 `set-depth` 均以 `UnsupportedDepthDefinition` 拒绝，
  未 staging / commit，拒绝前后文档快照不变。
- 12 次通过公共 `feature.set-depth` 将 blind boss 从 10 增厚至 25，均提交成功；
  贯穿几何保持。初始、增厚、只读重开后的体积与表面积均与独立解析公式相符，
  最大绝对差 `7.275957614183426e-12`，质心方向也符合所选平面与正反向。
- 每例保存后只读重开同一路径，获得新的文档和特征 ID；12 次旧特征 ID 读取均以
  `FeatureNotFound` 拒绝。重开后端条件、方向与 scope 等定义一致，诊断健康且未截断，
  rebuild 状态为 0、文档未修改，保存/打开均无错误或警告。
- 12 个 SLDPRT 实体的 SHA-256 与回执一致；同组宿主连续、清理错误为空，最终文档目录为空。

回执 SHA-256：`dcd8acf0aca8c4843847a76e23bed36607ec6ab2f8da00158847414131e690b9`。
本地复核记录 `a12-public-independent-audit.json` SHA-256：
`5a3a9bb05ed5e290a7316b4929ec0c3f163894b209f08c5c330425a7820416f9`，
与下载证据共同保存在 `/private/tmp/swcli-win-ci-40926208032`。

## 原 CI 开发包

同一 CI 的 artifact `12919748095` 已归档，ZIP SHA-256 为
`e01f0636a762bbcb34db5ee932aaad0174e6a9a6e483c86e6e1a439f6d46b6b8`，与 GitHub 一致。
包元数据为 `0.1.0a12.dev0`，sdist 含公共贯穿门禁源码；原包未重新打包。

| 原始产物 | SHA-256 |
| --- | --- |
| `swcli-0.1.0a12.dev0-py3-none-any.whl` | `c87ca42ced219edd455ca9f143b8820ae7d755293a29be17eaa4d79686cafb3b` |
| `swcli-0.1.0a12.dev0.tar.gz` | `aaa63b87aea065932f899a8d2675fd0be0e40419542f7f232ddff7907fe0f9e6` |

对上述原始 CI 包另行完成隔离安装与内容复核（未重新构建）：

- `twine check --strict` 检查 wheel / sdist 均通过；新建 Python 3.15 venv 安装原 wheel，
  `pip check` 无依赖冲突，实际导入位置位于该 venv 的 site-packages。
- wheel 与 sdist 的全部 60 个包源码 / schema / skill 文件，逐字节匹配提交 `2cd569c`；
  sdist 的全部 160 个测试和 CI 文件匹配提交。wheel RECORD 的 65 个带摘要条目均通过
  SHA-256 与文件大小校验，原始两个发布包的摘要仍与上表一致。
- 已安装包的三个协议 schema 和 42 个操作 schema 均通过 JSON Schema 元校验；
  公共贯穿 CLI 参数映射保留 document / lease / CAS，参数互斥及贯穿带深度（含 null）的
  四项拒绝成立；`sw-cli feature cut-extrude --help` 和内置 skill / usage 资源可用。
  检查期间主动阻止 COM 模块导入，确认客户端校验未加载原生 COM。

安装检查与内容检查分别保存为原开发包归档目录中的 `installed-audit.json` 和
`payload-audit.json`，SHA-256 分别为
`255c3cfd333232b053a11829ed3293711adc99b2e3ef0ba4dd8829a229d85946` 和
`f28db826d5437a5578036d4dcb7c93f02708fcc45966330549504e9870335f19`。
此处仅为无 COM 客户端安装和包内容校验；原生运行证明见前述 Windows 完整门禁。

## Docker 候选边界与剩余验收

DockerSW `codex/a12-candidate` 在 Windows 证据核对后固定上述 SWCLI 提交。
`ccfc520` 已隔离候选镜像发布与现用版本晋升：在此候选分支手动运行 `build.yml`，
显式设置 `promote_images=false`、`languages=zh-cn`。可发布 SHA 候选镜像并复用安装/构建缓存，
但仍运行完整 19 组、六个真实导出、可见宿主及本地化门禁。
候选不会更新 `2025` / `main` / `latest` 及其 CLI、语言别名。

候选固定提交为 `b3a754172a24a4008e924b1228a8f438ef4a36c9`，已启动
[DockerSW #193 / 40936007854](https://github.com/YJBeetle/DockerSW/actions/runs/40936007854)。
此后仅补充本文档，不替换正在验收的候选提交或重复触发运行。

DockerSW #193 已整条成功，下载归档并核对：

- `sw-cli-export-smoke-40936007854` artifact `12928303209`，ZIP SHA-256
  `b7a5dcd3b4593892938466e292c320e4ebac6d9a1051cc0324ab83c6e3312899`；
  `sw-language-smoke-40936007854` artifact `12928916674`，ZIP SHA-256
  `a4c816c0fb18fed6c34770d3aa0e8ef0397c4587f308bcd4a5bbe6a09ba7070b`。
  两个摘要均与 GitHub artifact digest 一致。
- 实际 daemon 为 `0.1.0a12.dev0`，Linux/Wine 的 full-plan 19 组 / 20 步全部成功；
  各组无清理错误、server exit 0，启动前和停止后原生进程目录均确认为空。
- 公共贯穿 12 例独立复核全部通过，包括 CLI 创建、公共增厚 10→25、贯穿编辑拒绝、
  同路径保存只读重开、fresh handles、定义及健康状态、源文件摘要与解析几何；
  最大几何绝对差为 `7.275957614183426e-12`，保存和打开均无错误或警告。
  同组宿主连续，未重试或组内重启。
- 共享 15 个导出、外层六个交付导出及中文本地化一个 STEP 共 22 个成功导出，
  实体大小与回执一致，文件头 / 容器 / XML 结构检查通过。中文 smoke 的 daemon 语言
  匹配守卫通过；visible-open 回执完成、宿主 visible=true 且前后一致、清理错误为空。
- 构建日志中的实际镜像为 `sha-b3a7541` 候选（含 CLI / zh-cn），
  `SW_PROMOTE_IMAGES=false`，未执行 branch/latest 别名晋升。

归档目录为 `/private/tmp/swcli-wine-ci-40936007854`；贯穿回执 SHA-256
`bdacdca33d3d90f951e533ad55588fb85662c1e502b5bbb816e73b8b77730a09`，
独立 12 例复核 `a12-public-independent-audit.json` SHA-256
`40da16aba5042e30fab7e971905065974930647a5727ac3317056eb93509760c`。

正式发布前须冻结 `0.1.0a12` 最终版本及提交，并验收该提交的原 CI 包；
当前 dev0 包不能作为正式 a12 发布。MacSW 暂不参与，本机 App 和容器不操作。

## 最终版本 Windows 验收

最终候选 `4fcf5b2dac178dff1e00ad6864cbcd805baa4612` 冻结 `0.1.0a12`，
产品代码仅版本号变化，新增未发布的说明文档。
[Windows CI 40946119790](https://github.com/YJBeetle/SWCLI/actions/runs/40946119790)
的双 Python 单测、打包及原生完整作业均成功。

原生 artifact `12932360248` ZIP SHA-256 为
`d18c02f214850ff42ff23c7b6a0f518e5fa8d35db4dcb923238fb2f242f8128e`，
与 GitHub digest 一致，归档于 `/private/tmp/swcli-win-ci-40946119790`。
完整 full-plan 19 组 / 20 步成功，实际 daemon 版本 `0.1.0a12`；各组清理无错误、
server exit 0、前后原生进程为空。共享 15 个实际导出匹配回执大小并通过格式检查。
公共贯穿 12 例再次逐项复核全部通过，包括公共增厚、只读重开、fresh handles、
拒绝无副作用、原生定义、健康状态、文件摘要和解析几何。最大几何绝对差
`7.275957614183426e-12`，保存 / 打开无错误或警告。
贯穿回执 SHA-256 `e082c975901ed2cc78214efd2ec9ab6f4fe3834a128cd8186696363f22892d0c`，
独立复核 SHA-256 `ac561e3c2324cd39ef0bdce61461c2b0722b1c899684e65f7f5ae163092c24fa`。

原包 artifact `12928413711` ZIP SHA-256
`886ab00dc50ec4b75db33103106c7fbd27cf8ea6e510fb33fa0c65b3a1ba3d5b` 与 GitHub 一致。
未重新打包的原始文件为：

| 最终版本原 CI 产物 | 字节 | SHA-256 |
| --- | ---: | --- |
| `swcli-0.1.0a12-py3-none-any.whl` | 211194 | `6a5c7c378b414a22b92c09698e5d54a572619a987de4cd214833018f6748c7d5` |
| `swcli-0.1.0a12.tar.gz` | 842099 | `ca04cd156b3fe57108c89d505e546733f0961fd375e3bbf0b12b18e6fa77320b` |

上述原包的严格 Twine、新 venv 安装、pip check、verify-installed 无 COM 检查通过。
60 个包文件与固定提交逐字节一致；sdist 的 160 个测试 / CI 文件匹配；
wheel RECORD 的 65 个带摘要条目正确。已安装客户端的 42 个操作 schema、三个协议 schema、
参数互斥及贯穿 depth（含 null）拒绝和内置 skill 资源检查通过。
原包及 provenance 位于 `/private/tmp/swcli-a12-ci-40946119790-dist`；
安装复核 SHA-256 `bdcc65cafd2b101e0d34c702d60bcc22d196229ab1f2a5479868f24c3c7c7fc1`，
内容复核 SHA-256 `dad5d6abfab12a4428c9e7e6ec3217bfe20f776644644aed935a1ff57da46c26`。

现将候选分支 gitlink 固定至此最终版本提交，再以 `promote_images=false` 验收匹配 Wine 候选。
最终版本 Wine 回执及用户发布确认仍待完成。

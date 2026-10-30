# SWCLI a13 多边形开发候选验收（2026-10-30）

最新候选固定 SWCLI `8d6e5d319becc4b8a76691ea6dadbde50290e71c`，版本
`0.1.0a13`。最终版本 Windows 完整验收已通过，最终版本 Docker/Wine 尚待对应运行的完整回执。
下文保留 dev0 版本 `1ffc750` 的双宿主证明与首次外层 CI 超时历史。
此记录不构成 a13 发布，不改变正式 a12 镜像，也不涉及 MacSW 验收。

## Windows 原 CI 与公共路径

[SWCLI 40973191895](https://github.com/YJBeetle/SWCLI/actions/runs/40973191895)
双 Python 单测、wheel/sdist 和原生安装/建模/导出作业全部成功。
运行关闭 `calibrate_polygon` 和 `calibrate_through_all`，本次证明来自安装后的公共 CLI，
不是内部原生校准代替公共操作。

原生 artifact `12943686649`，ZIP SHA256：
`38f859daded6e4adca16121fed5eb62d58e4a40e705648dae6062a5976214978`，与 GitHub digest 一致。
`hidden/runtime-sets/runtime-sets.json` 为 full/full-plan、completed/success，
`diagnostic_set=null`，19 组/20 步全部成功。各组 `cleanup_errors=[]`、server exit 0，
启动前和停止后的原生进程目录为空，实际 daemon 版本为 `0.1.0a13.dev0`。

原 `native-model` 组新增的 `polygon-model` 为 48 个公共组合：三角形/L 形 × 顺逆时针 ×
blind boss/cut × front/top/right × 正反向。组内同一隐藏 owned 宿主连续，未重启或失败重试。
下载后逐例独立核对：

- 创建回执为 `sketch.polygon`，完整唯一端点闭环、单个 closed contour、准确方向和原生草图句柄；
  后台创建保留前台及 session current，没有恢复 warnings 或编辑残留。
- 全部公共创建/只读重开的解析体积、表面积和按标准平面基底计算的世界质心一致，
  最大绝对差 `1.8189894035458565e-12`。48 个 SLDPRT 的 SHA256 与回执一致。
- 逐例租约冲突/CAS/跨文档读取拒绝；24 次多边形贯穿切除以既有
  `UnsupportedDimensionProfile` 拒绝，48 次 polygon feature 深度编辑以
  `UnsupportedDepthProfile` 拒绝，mutation 四标志均为 false，未 staging/commit。
- 保存 `save_errors=0`，标量 SaveAs3 没有 warning 输出，`save_warnings=null`；
  只读重开同一路径，打开 errors/warnings 均为 0，文档/草图/特征得到新 ID，旧 ID 全部拒绝。
  重开后的边闭环、blind 端条件/深度、完整健康诊断、needs_rebuild=0、clean 和文件字节保持。
- 原公共 through-all 12 例仍全部成功；15 个真实导出回执与实体 size 一致，格式头或
  容器结构通过（STEP 3；STL/3MF/AMF/GLB/PDF/DWG 各 2）。独立 visible smoke 成功，
  visible=true，前后宿主一致，清理错误为空。

多边形回执 SHA256：
`88583a6c83601c844647546aaf11bf2248f0c6b1e763ab2c6015ebb3f08fd0fb`。
完整运行摘要 SHA256：
`f9333b35f728700b252f9a1e1ea36230c32d67eda8d347ce3a21c47818c983a1`。
独立审计 `a13-public-independent-audit.json` SHA256：
`877ee90d6b1079c478bd9171ae555c043a9fe37cb630424285ae21955e7001cc`，
与下载证据共同保存在 `/private/tmp/swcli-win-ci-40973191895`。

## 原 CI 开发包

artifact `12941382148` 原 ZIP SHA256：
`6c4dff9890e9fa478c462b2c2a53ebc44ae8dbdc6505b1aa83eadaf7e4005ba7`。

| 原始产物 | 字节数 | SHA256 |
| --- | ---: | --- |
| `swcli-0.1.0a13.dev0-py3-none-any.whl` | 217265 | `2f733aa449322368a4e5b5a23be1f24c66174a6258663b42977f2aa3a1377308` |
| `swcli-0.1.0a13.dev0.tar.gz` | 863551 | `404aeb9385e7281036535980d219219da33ece0b2638ed3d7700a6e983b8b557` |

62 个包源码/资源逐字节匹配上述提交；sdist 新公共多边形门禁/协调器/两项新测试文件匹配。
原包保存在 `/private/tmp/swcli-a13-ci-40973191895-dist`，没有本地重新打包冒充原包。
这些是 dev0 开发包，不能作为正式 a13 发布资产。

## Docker/Wine 候选边界

独立工作树和 `codex/a13-candidate` 分支仅固定 Windows 已验收的上述提交。
沿用现有候选隔离机制，手动 `build.yml` 必须显式 `promote_images=false`、
`force_rebuild=false`、`languages=zh-cn`，只发布 SHA 候选镜像并复用安装/构建缓存。
完整 Wine19/公共多边形48/原贯穿12、六个交付导出、visible/localized 门禁与镜像身份仍须核对。
没有对应 Wine 证据前不宣称 Wine 已验收，不更新 2025/main/latest 或语言/CLI 现用别名。
最终版本冻结与原 CI 包/双宿主验收完成后再提交发布确认。MacSW 保持不动。

## 原开发包独立安装与载荷收尾

在 Wine 候选运行期间对上述原始 CI wheel/sdist 完成独立校验，没有重新打包：

- Twine 严格检查通过；wheel 的 67 个 RECORD 带摘要条目全部校验 SHA256 和字节数。
  sdist 中 62 个包源码/资源及 166 个测试/CI 文件逐字节匹配 `1ffc750`。
- 全新 `/private/tmp/swcli-a13-original-ci-install` venv 安装原 CI wheel，`pip check`
  无依赖冲突，`-I` 隔离 CLI、包资源与安装元数据一致；43 个请求、43 个结果、3 个协议
  Schema 均通过元校验。多边形 CLI 保留 document/lease/CAS，并拒绝四类非法嵌套顶点请求。
- 检查期间主动阻止 pythoncom/win32com/pywintypes 导入，客户端未请求加载原生 COM。
  此处证明客户端安装/包契约，原生建模证明仍见 Windows 完整回执与待完成的 Wine 门禁。

`installed-audit.json` SHA256：
`1367a050cf7d5fee870465ed6f848426564bc755b14ab06850c0fbcfdec717b7`；
`payload-audit.json` SHA256：
`0c85b26f340e4c47fec75305a992f4db61ca86560e846c4e6d95bff734e819b2`。
两份记录保存于原 CI 开发包归档目录，原始 wheel/sdist 摘要保持不变。
正在验收的 Docker 运行仍固定候选 `d0d0676`，不因这项文档收尾替换提交或重复触发。

## 首次 Wine 完整运行：外层 CI 预算耗尽

[DockerSW 40979321141](https://github.com/YJBeetle/DockerSW/actions/runs/40979321141)
固定 `d0d0676` / SWCLI `1ffc750`。未通过完整验收，失败原因是 GitHub Actions
`Shared isolated functional test sets` 整步 60 分钟截止：
`2026-10-30T01:42:30Z The action ... has timed out after 60 minutes`。
此时前 17 组成功，第 18 组 rectangle-right 刚开始，toolbox 未运行；没有已记录的
原生调用超时或 CAD 断言失败。visible/localized/promotion 后续步骤未运行，不能宣称整条通过。

下载 artifact `12947293565`，ZIP SHA256
`5068e3cd1f556f7736da9a15708ecaf2435b7639d2edb41c7033658595f13d21`
与 GitHub digest 一致，保存在 `/private/tmp/swcli-wine-ci-40979321141`。
`runtime-sets.json` 明确 `completed=false`、`success=false`。
native-model 组耗时 1599.823 秒（约 27 分钟），仍在每组 1800 秒限制内；
该组全部 48 个公共多边形案例已完成，同宿主、完整边闭环、解析几何/质心、拒绝边界、
保存只读重开及 48 文件哈希独立复核通过，最大差 `1.8189894035458565e-12`。
原贯穿组及其他前 17 组也完成，已完成组清理无误；中断组没有完整退出证明。
这份部分证据不替代缺失的完整 19 组、visible/localized 和镜像验收。

多边形回执 SHA256：
`d8748c41bf69c9ea0461d129113cca51a3bc8c523c10af3ac7996b6a5f9c3335`；
`a13-wine-partial-audit.json` SHA256：
`487ad78277ec9d18ca0d9ecf2139299b89e9866d8b4bed5d3ec7eb81383e9741`。

修复仅将 GitHub Actions 完整矩阵外层预算从 60 调整到 90 分钟，以容纳新增约 27 分钟
的公共多边形矩阵和原有全部功能组。产品原生 600 秒、共享请求/每组 1800 秒限制、
几何断言、首失败退出、组内不重启及不重试原生失败的策略均不变。
没有修改 SWCLI 产品或重新校准；后续候选仍须完整重新验收，不以本次部分通过晋升镜像。

## 修复后 Wine 开发候选完整通过

[DockerSW 40988415338](https://github.com/YJBeetle/DockerSW/actions/runs/40988415338)
在候选 `449eb72c8c9e7136ba6f79912eddbf68a7028406`、同一 SWCLI `1ffc750` 整条成功。
整步完整矩阵耗时约 65 分钟，90 分钟外层预算足够；没有改原生请求或每组期限。

- 导出/完整功能 artifact `12951911017`，ZIP SHA256
  `54b523cc34dec914b9b5ecf9b3a2d059b1832ee11ad5df50dcce574ed529ab88`；
  中文 artifact `12951248578`，ZIP SHA256
  `3c77b87c4039aa822df04422408b09b3b8ae3738371d34574dac12c8e882a5a8`。
  均下载并匹配 GitHub digest，归档 `/private/tmp/swcli-wine-ci-40988415338` 及 `-language`。
- full/full-plan 19 组/20 步全部 completed/success，diagnostic_set=null，实际 daemon dev0；
  每组 cleanup=[]、server exit 0，启动前/停止后原生进程目录为空，组内宿主保持。
- 48 个公共多边形全部独立复核通过，包含解析体积/表面积/固定平面世界质心、完整闭环、
  lease/CAS/跨文档及旧句柄拒绝、24 次贯穿范围拒绝、48 次深度拒绝且 mutation 全 false、
  同路径只读重开后的 fresh doc/sketch/feature IDs、健康/未截断/rebuild0/clean、48 文件哈希。
  最大绝对差 `1.8189894035458565e-12`。原 through-all 12 例全部通过。
- 15 个共享导出、六个交付导出与一个中文 STEP 共 22 个实体，与回执 size/格式头/容器
  结构一致；visible 回执完成，visible=true/前后宿主一致/cleanup=[]。实际日志明确
  `[CI language] zh-cn UI language and real STEP export verified.`
- 实际推送清单为 `sha-449eb72`（含 CLI/zh-cn），日志环境 `SW_PROMOTE_IMAGES=false`，
  最后执行 `[CI candidate] Verified SHA images retained; release aliases unchanged.`
  未执行 2025/main/latest 或语言/CLI 现用别名晋升。

多边形回执 SHA256：
`0b4c971776f6fb62df9b83642d0d2f37021ac454a7e4b798289330d0cca54fb7`；
完整运行摘要 SHA256：
`1762db62deb82e7fd281c7515c66fbc1a20274c3c1c9c30a1ded66a44e4df5f6`；
`a13-wine-independent-audit.json` SHA256：
`3c7ab85416e1a624883b6b96e278e5ac7f89f0585f6449cc745119a5f4db899a`；
`delivery-audit.json` SHA256：
`f16e9124981dd7289599ab18058ebd22cf8b795bcecc433e8788c5eabc03b244`。

以上完成 dev0 源码候选的 Windows/Wine 双宿主证明。正式 a13 仍须冻结最终版本/提交、
核验对应原 CI 包与最终版本运行回执，再由用户确认发布；不以 dev0 包冒充最终版。

## 最终版本 Windows 与原 CI 包

冻结提交 `8d6e5d319becc4b8a76691ea6dadbde50290e71c`，精确版本 `0.1.0a13`，
产品仅变更版本字串，CAD 代码与 dev0 已验收源码一致。
[Windows 40997158405](https://github.com/YJBeetle/SWCLI/actions/runs/40997158405)
整条成功；最终版本原生 artifact `12953127000` 的原 ZIP SHA256：
`7d90d5b789e9091e5948341669e9c6856bc6b05bc7f89b5aba21e1edc6af8227`，与 GitHub digest 匹配。

独立下载检查最终版本 full19/20 步、全部 48 公共多边形、原贯穿12及15真实导出均通过。
各组清理为空、server exit 0、前后原生进程为空；实际 daemon 版本为 `0.1.0a13`。
48 例端点闭环、解析体积/面积/世界质心、拒绝边界及 mutation=false、保存只读重开、
fresh/retired 文档/草图/特征句柄、完整健康诊断/clean/48 原生文件哈希逐项通过。
最大绝对差 `1.8189894035458565e-12`；独立 visible 检查前后宿主一致且清理为空。

多边形回执 SHA256：
`2d0cea9e4416fe38128373f4b1d532f21c2c0eb4b62a430796de228331baa347`；
完整运行摘要 SHA256：
`7353c2d5ea686561a3c2019ee04a673ae7309837f1c58eef2616b32c1d454c65`；
独立 `a13-public-independent-audit.json` SHA256：
`3f53bd9a681015197260bba9b118ea216095d42e0eabc9c7b633127c97f000a3`。
归档 `/private/tmp/swcli-win-ci-40997158405`。

同一运行的最终版本原始包 artifact `12952146065` 已独立核验：

| 原始产物 | 字节数 | SHA256 |
| --- | ---: | --- |
| `swcli-0.1.0a13-py3-none-any.whl` | 217190 | `3f0687617de8f50e8e96cc1c1aeb619c1b0fb4e239de8f0d8bbc240f7c6131c5` |
| `swcli-0.1.0a13.tar.gz` | 865011 | `3d87a8f716b3ebb8646267d33b2ed3d63b924bb58365df0a6033eb326d04c11d` |

原 ZIP SHA256：`dc97548517b9928d1d1c76e58fb939f343d342c38fb84ccd9f4069ddf4d4d138`，
与 GitHub digest 一致。62 包文件、sdist 62包/166测试CI及最终 release note 逐字节匹配
冻结提交；67 RECORD 哈希/大小全部通过。Twine严格/verify-sdist、新 venv 原包安装/
pip check/隔离 CLI 与资源/43请求43结果3协议 Schema 元校验、嵌套参数拒绝/无 COM 均通过。
`provenance.json` 在 `/private/tmp/swcli-a13-ci-40997158405-dist` 记录原 run/artifact/head/资产；
`installed-audit.json` SHA256：
`6aebb0ecb358d05bcd6f48aa2527568ad025be330475802190d8da3b5a42b691`。
没有使用本地重打包代替原 CI 包。最终版本 Wine 仍须同一冻结版本的完整运行证明，
不以 dev0 Wine 回执代替；未创建 tag/release 或晋升正式镜像。

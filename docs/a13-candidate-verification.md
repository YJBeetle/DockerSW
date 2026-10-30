# SWCLI a13 多边形开发候选验收（2026-10-30）

固定 SWCLI `1ffc7508761845a730f3be494e01edc9328597ef`，版本
`0.1.0a13.dev0`。本候选已完成 Windows 完整验收，Docker/Wine 尚待对应运行的完整回执。
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

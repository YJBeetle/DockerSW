# SWCLI a15 文档属性候选

本候选基于 DockerSW `7ad8caf7e5af28e1c85c03e3a24a643b80be902c`，包含
`e7afe38593bf97458c80b979c00bbb3313dcb0d1` 的 Wine 0020 XML 空命名空间修复，
以及此后字体和运行环境更新。基础提交的 Docker CI
[41987588899](https://github.com/YJBeetle/DockerSW/actions/runs/41987588899)
已成功。候选开发版完整 Wine 验收也已通过并独立复核。

固定 SWCLI `f8155e12b7b9e1aada2a53bdff3a1e498f9cfff0`，
版本 `0.1.0a15.dev0`。相对 Windows 已验收提交只修改测试路径映射、可选
Wine 另存验证和验收记录，产品代码与原生读取适配层相同。

## Windows 公共验收

[41990395318](https://github.com/YJBeetle/SWCLI/actions/runs/41990395318)
在 SWCLI `3bccdef` 通过。原始 ZIP 摘要与 GitHub 一致，独立复核了零件和装配的
16 次公共 CLI 读取、2 次过期戳拒绝、同名配置属性隔离、后台会话保持、只读重开
新句柄和文件哈希。现有 full19/20、polygon48、throughall12、15 导出和 visible
均通过，宿主连续，进程边界及清理正确。

| 原始证据 | SHA-256 |
| --- | --- |
| 原生 ZIP，artifact 13401035862 | `02bc051a35224b208b0abd51a8d525685fe754833a153dd2e8f3cea8538113cf` |
| 属性 CLI 回执 | `7ce3e7d7f3d2098617ab67090ba8c511eaf943ea9f738ede57f773f9845e0144` |
| 原始包 ZIP，artifact 13398545058 | `00c7e31ab84c8ff156444ecc7b04393ea619b06ad25d8a43b28128e191abc897` |

64 个 wheel 包文件、70 行 RECORD 和 sdist 的 234 个包/测试/CI 文件与测试提交
逐字节匹配。

## Wine 属性持久化验收接线

从上述 Windows 原生 artifact 提取两个已校验哈希的测试样件，下载使用工作流的
GitHub token 和 Actions 只读权限。样件为临时测试输入，随证据记录来源。
共享脚本通过公共 CLI 打开它们，验证读取后另存至新 SLDPRT/SLDASM，再关闭和只读
重开，检查属性值、原始输入文件哈希和另存文件哈希。该步骤验证 Wine 下属性的
实际 XML 保存持久化。随后仍执行既有完整功能矩阵。

候选手动构建使用 `promote_images=false`、`force_rebuild=false`、
`languages=zh-cn`。正式发布待最终版本验收及用户确认。

## 首次候选 CI 接线失败

[42001380892](https://github.com/YJBeetle/DockerSW/actions/runs/42001380892)
在逻辑测试阶段失败，镜像构建和原生 CAD 步骤未执行。
首个失败为 `test_each_phase_preserves_its_failure_code_and_log_after_collection`，
另一个失败为 `test_successful_phases_share_container_without_daemon_restart`。
新增的 `docker exec --env` 参数改变了证据测试识别命令的位置，测试模拟器因而未识别
共享验收命令。

将属性样件环境变量移至已有的常驻容器创建参数，与其他验收环境变量一同传入。
恢复共享步骤原有的 exec 命令形式，并在证据测试中检查该容器环境变量。
相关 37 项检查通过。额外覆盖属性验证失败时传播错误码、保留诊断并停止完整矩阵。

## 开发版 Wine 原始证据复核

[42005850194](https://github.com/YJBeetle/DockerSW/actions/runs/42005850194)
在 Docker `80a866312538270b930e2144b9da89987ad56cdd`、SWCLI `f8155e1` 完成。
两个原始 ZIP 均与 GitHub 摘要一致。公共 CLI 在同一隐藏 owned 宿主读取零件和装配，
共 16 次成功属性读取和 2 次过期戳拒绝；空属性与缺失名称区分，配置专属同名值未串入
文档级结果，读操作前后描述符保持一致。

两种文件均通过真实 `document save-as` 另存到新路径，原生返回 errors=0、warnings=null，
随后关闭并以新文档句柄只读重开。中文、英文、空文本、数值、布尔五行的原值、求值、
原生类型和解析标志保持一致。另存文件大小与回执一致，原输入和另存文件哈希分别复核。
该结论仅覆盖这两类实际样件，未据 XML 探针宣称其他保存场景通过。

既有 full 19 组 20 步、48 多边形、4 次深度写入与 4 次同深度调用、12 贯穿、
15 共享导出、6 交付导出、1 中文 STEP 和 visible 均通过。各组清理无错误、server exit 0、
进程边界为空。日志确认实际中文 UI/STEP、`SW_PROMOTE_IMAGES=false` 和
`Verified SHA images retained; release aliases unchanged.`，候选仅保留 `sha-80a8663` 镜像。

| 原始证据 | SHA-256 |
| --- | --- |
| 导出 ZIP，artifact 13410400228 | `270769a07a9a7091b3d9d9a9bca9d17c142f4d55647b50e5b10416b2d777387d` |
| 中文 ZIP，artifact 13410535090 | `9ff84b050aba0dd7359ea8aa55ac435574b60952f74756c540218e56f346393f` |
| 公共属性回执 | `49a54426d2a037eb648621132b19257ea2ce161be42083e26f38a783bfa360b2` |
| 完整矩阵摘要 | `7ee63a2e13d8a4c5ad0ea491aa644988e65e2a3eddb7e5e5a3ca25d63c3a59cd` |
| 多边形回执 | `3a1260fe38c90547252b42961193b3c38a49653950b87e77c682de788f7a4aed` |
| 另存 SLDPRT | `6c3c11b2fa6b2ecdbd0d7980582f23718e9f26305b826545734a61dfe210088c` |
| 另存 SLDASM | `ba0cc1eff53b313bfbd0952e444d813d71dc54eedf0570c618f97d16258134a7` |
| 实际构建日志 | `735f8be86c34355b9c030c9a9a859c8e87eef0e6ab293d791ef9f4b21659be39` |

Windows 原 CI wheel/sdist 另已通过 Twine strict、sdist 检查、全新隔离环境安装、
`verify-installed.py`（不激活 COM）和 `pip check`。开发版证据齐全，接下来冻结精确
`0.1.0a15` 并进行最终 Windows/Wine 及最终原 CI 包验收；尚未发布或晋升镜像。

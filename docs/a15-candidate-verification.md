# SWCLI a15 文档属性候选

本候选基于 DockerSW `7ad8caf7e5af28e1c85c03e3a24a643b80be902c`，包含
`e7afe38593bf97458c80b979c00bbb3313dcb0d1` 的 Wine 0020 XML 空命名空间修复，
以及此后字体和运行环境更新。基础提交的 Docker CI
[41987588899](https://github.com/YJBeetle/DockerSW/actions/runs/41987588899)
仍在运行。候选完整 Wine 验收待该基础 CI 成功后触发。

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

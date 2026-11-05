# A16 发布与 Windows 验收

[SWCLI v0.1.0a16](https://github.com/YJBeetle/SWCLI/releases/tag/v0.1.0a16) 已公开为预发布版本，标签与 Windows 验收源码均为 `8256ee290c18d0809afaf78d4d5b09c5ab119918`。

[最终 Windows CI 42089485924](https://github.com/YJBeetle/SWCLI/actions/runs/42089485924) 的原始产物已独立核验。两类样件的五个摘要字段写入、文本自定义属性文档/配置作用域读写与隔离、CAS/只读拒绝、另存只读重开通过。现有完整 19 组 20 步、48 多边形、4 写入/4 同深度、12 贯穿、15 真实导出、visible、宿主连续与清理也通过。私有样件校准独立标记为诊断，不替代公共验收。公共 metadata 没有低层 setter trace，不把命令回执当作该 trace。

公开五资产已匿名下载逐字节核对，清单匹配。wheel 为原 CI 包 226684 字节，SHA-256 `c310b54d3a48028318b95cbb63e8adc2df6bb11f34abe84d7714d09c0e46d2c1`；sdist 为原 CI 包 898239 字节，SHA-256 `09b33d39b84eb19872658f026be8eaaaa9b82acc531863d344a9a60fcc8493e3`。源码、资源、RECORD、Twine、sdist 与全新隔离安装检查通过。

DockerSW 2025 指针更新到该精确 A16 提交，属性输入改用上述最终 Windows run 的 artifact `13448106095`，ZIP 与两份文件摘要均显式固定。本提交不声明新的 Docker/Wine 运行或镜像晋升成功；自动 push 流水线仍须按原有完整门禁执行。保留 600 秒原生、1800 秒每组、90 分钟外层与首失败退出，无原生失败重试、自动回滚或组内重启。

A17/A18 的选项文档属性独立开发；main 中 MCP 的未提交代码不随本次指针更新进入镜像。

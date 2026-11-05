# SWCLI a15 最终发布审阅

状态：双宿主与最终原 CI 包已验收，等待所有者最后确认。尚未创建 tag、Release（含 draft），尚未晋升镜像，公开下载核验尚未执行。

## 发布内容

- SWCLI `0.1.0a15`：文档级自定义属性只读列举/查询，保留原生类型、原值、求值与缓存/解析标志，区分空值和缺失名称；沿用后台/session/CAS/state 检查。
- 已验证零件和装配样件；配置属性读取、公共属性写入和工程图样件留待后续。
- 计划 tag `v0.1.0a15` 精确指向 `86b6b38e6cc78810463130c2e141bb22da9ed621`，以 prerelease 发布 Windows 最终 CI 原始 wheel/sdist，原包不重新构建。保留 `16075bd5c68f8f2898310a8b5763c6eb85972b87` 的真实 merge 祖先及随包 API 指南。

## 通过的最终门禁

- [Windows 42022223755](https://github.com/YJBeetle/SWCLI/actions/runs/42022223755)：原生 ZIP 摘要匹配，公共属性 16 次读取/2 次 CAS 拒绝；两类文件的 scope/空值/缺失名、后台读/状态保持、只读重开新句柄/输入哈希全部通过。私有校准独立记录，不冒充公共门禁。
- [Wine 42031035051](https://github.com/YJBeetle/DockerSW/actions/runs/42031035051)：Docker `0130790989c37679bdb008db255ac195cd735d5b` 固定同一最终 SWCLI，含 0020 修复。真实另存到新 SLDPRT/SLDASM，关闭后只读重开；属性原值、求值、原生类型、输入和另存文件哈希、同宿主/清理通过。
- 两宿主均通过现有 full19/20、polygon48（4 次深度写入/4 次同深度）、through-all12、15 共享导出及 visible；Wine 另通过 6 交付导出、1 中文 STEP 和中文 UI。
- 原 wheel/sdist 与源码资源逐字节匹配，RECORD、sdist、Twine strict、全新隔离安装、CLI schemas/指南、pip check 通过。

## 不变字节的原 CI 资产

| 资产 | 字节 | SHA-256 |
| --- | ---: | --- |
| `swcli-0.1.0a15-py3-none-any.whl` | 222274 | `15a6ef0641ca4fedf959c8b03be57adb1cc28522162cea3190f7b3ee92e5089a` |
| `swcli-0.1.0a15.tar.gz` | 889837 | `b3a2f0331af2767ecf2dde3eb90c3996de597bd87dfabc49868d4d4cb0096030` |

原始 dist artifact `13412022527`，run `42022223755`。
来源与完整证据见 [a15-release-provenance.json](a15-release-provenance.json)；原始回执哈希见 [a15-candidate-verification.md](a15-candidate-verification.md)。
本地可审阅资产在 `/private/tmp/swcli-a15-release-ready`，含 `RELEASE_NOTES.md`、原 wheel/sdist、`provenance.json` 与 `SHA256SUMS`。

## 获批后的具体动作

1. 创建上述精确 tag 和 prerelease，上传原包及说明/来源/校验清单，匿名下载后逐字节核对。
2. 将已验收 Docker runtime SHA `0130790` 非强制快进到正式 `main`/`2025`，复核既有 fast-path 晋升实际执行，核验 30 个普通/CLI/中文别名摘要。当前远端 main=`6aff196`、2025=`7ad8caf` 均为候选祖先；执行前重新核对，保留他人后续提交，若分叉则在隔离候选中合并并完成必要验收。
3. 完成后将实际发布、晋升和公开下载证据补入 provenance；审阅文档提交不充当验收镜像 SHA。

本轮监控到此结束；发布行为等待用户最终批准。

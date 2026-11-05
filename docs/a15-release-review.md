# SWCLI a15 最终发布审阅

a15 已公开预发布。匿名下载的 wheel 和 sdist 与最终 Windows CI 原包逐字节一致。[SWCLI v0.1.0a15](https://github.com/YJBeetle/SWCLI/releases/tag/v0.1.0a15)

## 发布内容

- SWCLI `0.1.0a15`：文档级自定义属性只读列举/查询，保留原生类型、原值、求值与缓存/解析标志，区分空值和缺失名称；沿用后台/session/CAS/state 检查。
- 已验证零件和装配样件；配置属性读取、公共属性写入和工程图样件留待后续。
- 发布 tag `v0.1.0a15` 精确指向 `86b6b38e6cc78810463130c2e141bb22da9ed621`，以 prerelease 发布 Windows 最终 CI 原始 wheel/sdist，原包不重新构建。保留 `16075bd5c68f8f2898310a8b5763c6eb85972b87` 的真实 merge 祖先及随包 API 指南。

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

## DockerSW 发布分支

归档时远端 `main` 与 `2025` 均指向 `69a657e`，固定上述 a15 SWCLI，并包含后续 Wine 修复。
候选 Wine 门禁的运行时提交是 `0130790`。镜像标签的实际摘要另行核验。

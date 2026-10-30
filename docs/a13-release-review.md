# SWCLI a13 发布记录（已批准并公开）

状态：用户于 2026-10-30 明确批准发布；GitHub pre-release 已公开，原包匿名下载校验和 Docker 正式镜像晋升均已完成。
MacSW 未操作；此前验收与等待批准的历史保留在 Git 记录中。

## 已发布内容

- GitHub pre-release：[SWCLI v0.1.0a13](https://github.com/YJBeetle/SWCLI/releases/tag/v0.1.0a13)。
- tag `v0.1.0a13`，精确冻结提交 `8d6e5d319becc4b8a76691ea6dadbde50290e71c`。
- 原包来自最终 Windows CI `40997158405`、artifact `12952146065`，不重新构建。
- wheel `swcli-0.1.0a13-py3-none-any.whl`，217190 字节，SHA256
  `3f0687617de8f50e8e96cc1c1aeb619c1b0fb4e239de8f0d8bbc240f7c6131c5`。
- sdist `swcli-0.1.0a13.tar.gz`，865011 字节，SHA256
  `3d87a8f716b3ebb8646267d33b2ed3d63b924bb58365df0a6033eb326d04c11d`。
- 本地审阅目录 `/private/tmp/swcli-a13-release-ready` 已复制原始两份包，并准备
  `SHA256SUMS`、`provenance.json` 与 `RELEASE_NOTES.md`，并归档独立审阅证据。
  最终 Wine 证据已补齐，原 wheel/sdist 字节保持不变。

## 功能与边界

新增 `sketch polygon --plane front --vertices-mm '[[0,0],[20,0],[0,15]]'`，
支持三标准面上的 3–64 点简单闭合轮廓、顺逆时针和凹多边形；精确草图句柄可用于现有
blind 拉伸/切除。嵌套参数及几何在 CAD 前校验，原生关闭/求解后核对完整唯一端点闭环、
单 closed contour、面积/周长/质心；部分失败保留准确存活句柄，恢复失败不能成功。

没有孔、弧、自动修复、驱动尺寸或完全约束保证；不扩展贯穿切除或深度编辑的轮廓范围。
lease/CAS、后台/current 恢复、600 秒原生限制、严格断言、不重试/自动回滚/组内重启均保留。
用户升级时 client 和 daemon 使用同一版本。

## 最终验收

最终 Windows [40997158405](https://github.com/YJBeetle/SWCLI/actions/runs/40997158405)
已下载独立核验：精确 daemon `0.1.0a13`、full19/20步、public polygon48、原贯穿12、
15真实导出、visible、清理和宿主连续性全部通过。原 CI 包的 SHA/source/67 RECORD/
Twine/全新隔离安装/43请求43结果3协议 Schema/资源和无 COM 校验均完成。

最终 Wine [41001608607](https://github.com/YJBeetle/DockerSW/actions/runs/41001608607)
固定 Docker `a3a5976` 与同一 SWCLI `8d6e5d3`，整条成功并下载独立严核：
精确 daemon `0.1.0a13`、full19/20步、polygon48/throughall12、22真实导出、visible/localized、
逐例几何/保存重开/句柄拒绝/清理/进程与组内宿主连续性全部通过。
实际日志验证 `SW_PROMOTE_IMAGES=false`、`sha-a3a5976` CLI/中文候选镜像清单及
`[CI candidate] Verified SHA images retained; release aliases unchanged.`，候选验收阶段未晋升现用标签；用户批准后的正式晋升另见下文。

详细证据见 [候选验收记录](a13-candidate-verification.md)；机器来源记录见
[发布来源记录](a13-release-provenance.json)，运行与发布状态均已核验；release_created/public_download_verified 为 true，原包公开下载与正式别名摘要已独立核对。

## 用户批准与正式集成

用户明确回复“批准发布”后，公开 pre-release（不设为 latest 正式版），tag 精确指向
`8d6e5d319becc4b8a76691ea6dadbde50290e71c`。wheel/sdist 从最终 Windows 原 CI 包
上传，匿名重新下载逐字节和 SHA256 匹配；provenance/清单同步公开。

Docker main/2025 先快进至完整验收的 `a3a5976`，两条 push CI 复用该 SHA 的已验证镜像，
执行正式标签晋升；未触发重复原生完整矩阵。随后才同步纯文档验收/发布记录，
避免把文档提交 SHA 冒充运行验收镜像。

- 2025：[CI 41021426153](https://github.com/YJBeetle/DockerSW/actions/runs/41021426153) 成功，实际日志验证同 SHA 快速晋升。
- main：[CI 41021426274](https://github.com/YJBeetle/DockerSW/actions/runs/41021426274) 成功，实际日志验证同 SHA 快速晋升。

独立从 GHCR 读取 2025/main/latest 的普通/CLI/中文组合共30个别名，全部与
`sha-a3a5976` 对应清单 digest 一致，差异0。正式原始镜像和 CLI 变体均有检查，
未把 registry push 或源码打印当作验收证明。MacSW 保持不动。

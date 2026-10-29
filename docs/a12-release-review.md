# SWCLI a12 发布审阅

状态：用户已确认发布；[v0.1.0a12](https://github.com/YJBeetle/SWCLI/releases/tag/v0.1.0a12)
已于 2026-10-30（Asia/Shanghai）公开为 pre-release。tag 指向已验收的 `4fcf5b2`，
四个公开下载资产已重新下载核对，其中 wheel/sdist 与原 CI 包逐字节一致。
公开资产身份见 [发布来源记录](a12-release-provenance.json)。

## 待发布内容

- 名称：`SWCLI v0.1.0a12 — guarded one-direction through-all cuts`。
- tag：`v0.1.0a12`；指向 `4fcf5b2dac178dff1e00ad6864cbcd805baa4612`；GitHub pre-release。
- 原始 wheel：`swcli-0.1.0a12-py3-none-any.whl`，211194 字节，SHA-256
  `6a5c7c378b414a22b92c09698e5d54a572619a987de4cd214833018f6748c7d5`。
- 原始 sdist：`swcli-0.1.0a12.tar.gz`，842099 字节，SHA-256
  `ca04cd156b3fe57108c89d505e546733f0961fd375e3bbf0b12b18e6fa77320b`。
- 来源：Windows CI `40946119790` 的 artifact `12928413711`。使用原包，不重新打包。
- 审阅目录：`/private/tmp/swcli-a12-release-ready`，含两份包、SHA256SUMS、provenance 和发布说明。

## 功能和范围

增加公共 `feature.cut-extrude --through-all`，支持全圆 / 轴对齐矩形在三标准面上的
单向正反贯穿。与 depth 互斥，保留 lease/CAS、后台文档恢复、精确特征句柄和几何验证。
贯穿响应的深度为 null，`set-depth` 仍限 blind 特征。多实体、任意轮廓和双向贯穿暂不包含。

最终版 Windows 和 Wine 都通过 19 组 / 20 步完整门禁、公共贯穿 12 例，含公共增厚、
保存只读重开、fresh handles、原生定义、解析几何、源文件哈希和清理检查。
Wine 还通过六个交付导出、可见和中文 smoke。原 CI 包严格 Twine、隔离安装、源码及资源
完整性校验通过。详细运行、artifact 和摘要见 [完整验收记录](a12-candidate-verification.md)。

MacSW 本轮未参与；既有 a11 软件渲染复杂工程图重开超时的接受边界继续保留。
用户端需同时升级 client 和 daemon。

## 正式集成

SWCLI main 已快进到发布提交。用户同时授权 Docker 更新，DockerSW 的正式 main / 2025
已原子快进到完整 Wine 验收通过的 `aef7424`，固定同一 SWCLI 提交。
正式 CI 分别为 [main 40963021823](https://github.com/YJBeetle/DockerSW/actions/runs/40963021823)
和 [2025 40963021712](https://github.com/YJBeetle/DockerSW/actions/runs/40963021712)，
均已成功。实际日志确认 `SW_PROMOTE_IMAGES=true`，使用此前完整验收通过的
`sha-aef7424` 英文及中文候选镜像快进晋升；此处没有将跳过的原生测试冒充新运行的验收。

2026-10-30（Asia/Shanghai）另行直接读取 GHCR registry，核对 `sw-runtime`、
`sw-preinstalled`、`sw-executable` 的 `2025` / `main` / `latest` 默认与 CLI 别名，
以及后两仓库的 zh-cn / zh-cn-cli 别名，共 30 个 manifest digest，全部与相应
已验收 SHA 候选完全一致，无不匹配项。逐项摘要及两个作业日志摘要保存于
[发布来源记录](a12-release-provenance.json)，本地原始核对记录为
`/private/tmp/swcli-a12-release-ready/docker-aliases.json`。

a12 发布与 Docker 正式镜像更新均已完成。
MacSW 按用户明确要求保持不动。

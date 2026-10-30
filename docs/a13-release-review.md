# SWCLI a13 发布审阅（待最终 Wine 验收）

状态：未发布、未创建 tag/release；最终版本 Wine CI 仍在运行，尚未请求最后发布确认。
此材料用于提前审阅，不表示现用 Docker 镜像或 MacSW 已更新。

## 拟发布内容

- GitHub pre-release：`SWCLI v0.1.0a13 — simple closed polygon sketches`。
- tag `v0.1.0a13`，精确冻结提交 `8d6e5d319becc4b8a76691ea6dadbde50290e71c`。
- 原包来自最终 Windows CI `40997158405`、artifact `12952146065`，不重新构建。
- wheel `swcli-0.1.0a13-py3-none-any.whl`，217190 字节，SHA256
  `3f0687617de8f50e8e96cc1c1aeb619c1b0fb4e239de8f0d8bbc240f7c6131c5`。
- sdist `swcli-0.1.0a13.tar.gz`，865011 字节，SHA256
  `3d87a8f716b3ebb8646267d33b2ed3d63b924bb58365df0a6033eb326d04c11d`。
- 本地审阅目录 `/private/tmp/swcli-a13-release-ready` 已复制原始两份包，并准备
  `SHA256SUMS`、`provenance.json` 与 `RELEASE_NOTES.md`。最终 Wine 回执取得后更新
  provenance/清单状态，原 wheel/sdist 字节保持不变。

## 功能与边界

新增 `sketch polygon --plane front --vertices-mm '[[0,0],[20,0],[0,15]]'`，
支持三标准面上的 3–64 点简单闭合轮廓、顺逆时针和凹多边形；精确草图句柄可用于现有
blind 拉伸/切除。嵌套参数及几何在 CAD 前校验，原生关闭/求解后核对完整唯一端点闭环、
单 closed contour、面积/周长/质心；部分失败保留准确存活句柄，恢复失败不能成功。

没有孔、弧、自动修复、驱动尺寸或完全约束保证；不扩展贯穿切除或深度编辑的轮廓范围。
lease/CAS、后台/current 恢复、600 秒原生限制、严格断言、不重试/自动回滚/组内重启均保留。
用户升级时 client 和 daemon 使用同一版本。

## 验收与剩余条件

最终 Windows [40997158405](https://github.com/YJBeetle/SWCLI/actions/runs/40997158405)
已下载独立核验：精确 daemon `0.1.0a13`、full19/20步、public polygon48、原贯穿12、
15真实导出、visible、清理和宿主连续性全部通过。原 CI 包的 SHA/source/67 RECORD/
Twine/全新隔离安装/43请求43结果3协议 Schema/资源和无 COM 校验均完成。

最终 Wine [41001608607](https://github.com/YJBeetle/DockerSW/actions/runs/41001608607)
固定 Docker `a3a5976` 与同一 SWCLI `8d6e5d3`，**仍待完整结果与下载回执核对**。
需要 full19/20步、polygon48/throughall12、六交付导出、visible/localized、SHA候选身份、
清理和不晋升现用标签证明。开发版 Wine 成功记录不能替代该最终版本的验收。

详细证据见 [候选验收记录](a13-candidate-verification.md)；机器来源记录见
[发布来源记录](a13-release-provenance.json)，其中待验项明确为 false/null。

## 最后发布确认的范围

全部最终证据通过后，需用户确认 SWCLI pre-release 和 Docker 正式集成/镜像更新。
确认前不创建 GitHub tag/release（含 draft）、不推正式 main/2025 或晋升现用别名。
正式集成应先使用已经完整验收的 Docker 候选提交和同 SHA 镜像，随后再同步纯文档记录，
避免把文档提交误当新验收镜像。公开后还须匿名重新下载核对原包哈希，并核对正式镜像别名。
MacSW 按用户要求保持不动。

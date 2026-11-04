# SWCLI a14 候选验收

本候选固定 SWCLI `fff5e0a21362beb9f08b42c58924c811a484ade1`，版本 `0.1.0a14.dev0`。发布前要求合入的 `16075bd5c68f8f2898310a8b5763c6eb85972b87` 是该提交的祖先，原始安装包包含 SOLIDWORKS API 指南。

## Windows 公共门禁

[Windows installed full 41844896304](https://github.com/YJBeetle/SWCLI/actions/runs/41844896304) 通过。原始产物独立复核通过 19 组 20 步、48 个多边形、12 个贯穿切除、15 个真实导出及 visible 冒烟。对照原生进程清理、组内宿主身份、文件哈希以及保存后只读重开的深度、方向和几何。深度写入矩阵中的四例均通过。

| 轮廓 | 特征 | 平面与方向 | 深度变化（mm） |
| --- | --- | --- | --- |
| 三角形，逆时针 | 拉伸 | 前视，正向 | 10 → 14 |
| 凹 L，顺时针 | 拉伸 | 上视，反向 | 10 → 6 |
| 三角形，顺时针 | 切除 | 右视，反向 | 5 → 7 |
| 凹 L，逆时针 | 切除 | 前视，正向 | 5 → 3 |

四例的写入与同深度调用均核对 mutation 标志、选择释放和几何读回。公共回执同时覆盖租约冲突、版本戳冲突、跨文档句柄拒绝和多边形贯穿切除限制。

| 原始产物 | SHA-256 |
| --- | --- |
| 原生证据 ZIP，artifact 13336042422 | `ca6204fe48502f84813bb93a87bb54651ee16b311dffbd6d260d668d39a3c0a1` |
| 打包产物 ZIP，artifact 13330158338 | `5f5d4749ebec65ad1f639397ccd5d715f327350e13adc408d8a8e174df7fd4a5` |
| wheel | `dc6318334be9c9a5676e1f068d8ee344ca324116f6c0c591e0d6c8311da1df52` |
| sdist | `297d5c19bbb446bcb88a3aacac1024703979cfe1eff4834488fe6c7fa5b86e8c` |

两个 ZIP 的本地 SHA-256 与 GitHub Actions 摘要一致。已核对原始包版本、wheel RECORD 和 63 个 wheel/sdist 包文件与固定提交的字节一致性。

## Wine 候选门禁

同一提交等待 DockerSW 完整 Wine 门禁。候选分支使用 `promote_images=false`、`force_rebuild=false`、`languages=zh-cn` 手动触发，仅产出按提交 SHA 标识的镜像。正式发布另行确认。

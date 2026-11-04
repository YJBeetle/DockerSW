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

[Wine 完整门禁 41858683707](https://github.com/YJBeetle/DockerSW/actions/runs/41858683707) 通过。验收提交为 DockerSW `0bff69cedc813ead9d1cb95070b6bec4209e70e1`，其中 SWCLI 固定为本页开头的开发版提交。

从原始 ZIP 复核 19 组 20 步、48 个多边形、四次深度写入和四次同深度调用、12 个贯穿切除。四个改深度样件的保存重开定义、方向、几何、文件哈希均匹配，组内宿主身份、进程清理和 visible 冒烟通过。实际验证 15 个共享导出、6 个交付导出和 1 个中文 STEP。运行日志确认中文 UI 验证、`SW_PROMOTE_IMAGES=false` 和按 SHA 保留候选镜像，未晋升正式别名。

| 原始证据 | SHA-256 |
| --- | --- |
| 导出及原生回执 ZIP，artifact 13343973644 | `03e8ac7cdefb8da84958dfe7ae668175e4e0a59a346b8403f35b1474300eaece` |
| 中文冒烟 ZIP，artifact 13345171370 | `b9cc682145a2114b93236657ea2833b226380ef99081d3e7be812435e72eefa9` |
| 完整矩阵回执 | `5fe2f0b2d218f086e89b8a5f4e2d50e6c3e4ef7b6653bba0a1aa4b70c88d9738` |
| 多边形回执 | `7f683621ddeadc8c5a70b15accdc0d2eeb64030d575280c58b76264683f2c50c` |

正式版本 `0.1.0a14` 须重新验收精确版本的双宿主和原始 Windows CI 安装包，发布另行确认。

## 0.1.0a14 最终候选

本候选现在固定 SWCLI `0d966ec067f94560737bdb383fef5db314dcb54b`，精确版本 `0.1.0a14`。相对开发版只修改版本字串并添加发行说明。用户指定的指南分支提交仍是该提交的祖先。

[最终 Windows 公共门禁 41877115880](https://github.com/YJBeetle/SWCLI/actions/runs/41877115880) 成功。原始 ZIP 摘要与 GitHub 一致，独立复核通过 19 组 20 步、48 多边形、四次深度写入和四次同深度调用、12 贯穿切除、15 共享导出及 visible 冒烟。逐例核对解析体积、表面积、世界质心、重开深度和方向、保存文件哈希。创建及重开共 96 个完整端点环、48 个新草图句柄、96 次旧句柄拒绝、只读重开未修改、宿主连续和进程清理均通过。

原始 wheel 的 63 个包文件及 sdist 的 230 个源码/测试/CI/发行说明文件与最终提交逐字节匹配，69 行 RECORD 均核对。Twine strict、sdist 校验、新 venv 原包安装、隔离 CLI/schema/指南资源和 pip check 通过。

| 最终 Windows 证据 | SHA-256 |
| --- | --- |
| 原生 ZIP，artifact 13352561867 | `ead33143a52261343af4d23711769a0ca71a24f31ecb93ae4965fb4f9e42d484` |
| 包 ZIP，artifact 13347202298 | `729493e7dd2b12b91f090f21905c94c860eb59fa13135fd3c773d67b2934f7bc` |
| 原始 wheel，220008 字节 | `04b215ef680c68ac4065b0cc55d7588791d8ff688a005c40b1adb332a491107e` |
| 原始 sdist，878777 字节 | `b6db70c1c857f893a5d5640455e5471711c6bcabaa3081f3c58944a7bd6cd97d` |
| full 回执 | `46ba4e2ba08bd567878ff553135e773bb21ff2bb5954f8c1e6eb4c14ccf70f9a` |
| polygon 回执 | `576af093a7b76673c2918660a4c2e0668879ac8976cb571037cd7ae9c4931782` |

最终 Wine 完整验收待完成。手动构建使用 `promote_images=false`、`force_rebuild=false`、`languages=zh-cn`，正式发布须用户最终确认。

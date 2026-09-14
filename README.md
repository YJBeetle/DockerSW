# DockerSWPreinstalled

DockerSWPreinstalled 是仅在内网使用的私有构建与部署层。CI 从受控的内网存储下载完整、合法取得的 SOLIDWORKS 官方安装介质，调用 DockerSW 提供的 `sw-install` 完成 Wine 无头 MSI 安装，然后将成品推送到本项目的 GitLab Container Registry。

公开的 DockerSW 仓库负责 Wine 运行时、安装脚本和导出工具；本仓库负责安装介质来源、安装注册表、本地 FlexNet 服务和最终私有镜像。官方介质、序列号和许可证不得上传到公开镜像仓库。

## 流水线

1. `mirror_sw_runtime` 根据当前固定的 DockerSW 子模块提交，将 GitHub CI 已验证并发布的 `ghcr.io/yjbeetle/sw-runtime:sha-<短 SHA>` 原样同步到本项目的 GitLab Registry。相同标签已存在时直接跳过，不重新构建或跨网下载。
2. `build_sw_preinstalled` 只从内网的 `CI_REGISTRY_IMAGE/sw-runtime:sha-<短 SHA>` 拉取基础镜像。
3. 流水线从内网下载并校验安装介质，执行无头安装。
4. 最终镜像仅保留安装后的 Wine prefix 和本仓库的内部 FlexNet 服务，不包含 ISO、压缩包或安装日志。
5. 成品只推送到 GitLab Registry 的 `CI_REGISTRY_IMAGE/sw-preinstalled`，标签为 `latest`、`sha-<commit>`；Git tag 流水线还会推送同名版本标签。

## 安装介质配置

当前私有仓库已在 `.gitlab-ci.yml` 中固定内网 ISO 下载地址及其 SHA-256，默认流水线无需额外变量即可下载、校验并安装。下列同名 GitLab CI/CD Variables 可在不修改仓库的情况下覆盖默认值：

| 变量 | 要求 | 用途 |
|---|---|---|
| `SW_MEDIA_URL` | 已提供默认值；与 `SW_MEDIA_LOCAL_PATH` 二选一 | 内网 HTTPS、WebDAV 或对象存储中的完整介质归档 |
| `SW_MEDIA_LOCAL_PATH` | 与 `SW_MEDIA_URL` 二选一 | 私有 Runner 已挂载的介质文件 |
| `SW_MEDIA_SHA256` | 已提供默认值 | 介质 SHA-256，校验失败立即停止 |
| `SW_MEDIA_BEARER_TOKEN` | 可选、Masked | 内网下载 Bearer Token |
| `SW_MEDIA_USERNAME` | 可选、Masked | HTTP Basic 用户名 |
| `SW_MEDIA_PASSWORD` | 可选、Masked | HTTP Basic 密码 |
| `SW_INSTALL_TIMEOUT` | 可选 | 单个安装步骤超时秒数，默认 10800 |

`CI_REGISTRY`、`CI_REGISTRY_USER`、`CI_REGISTRY_PASSWORD` 和 `CI_REGISTRY_IMAGE` 使用 GitLab 自带变量，不再配置 Docker Hub 凭据。

`SW_RUNTIME_IMAGE` 可选；默认使用按 DockerSW 子模块短 SHA 镜像到 GitLab Registry 的 `sw-runtime`，只在需要临时覆盖基础镜像时设置。

介质可以是 ISO、ZIP、7z 或 tar 系列归档，但解压后必须包含：

```text
swwi/data/solidworks.msi
PreReqs/VCRedist17/VC_redist.x64.exe
PreReqs/dotNetFx/ndp48-x86-x64-allos-enu.exe
```

安装前会导入私有的 `assets/solidworks_reg/*.reg`。MSI verbose 日志可能包含序列号，因此只存在于临时安装阶段，不复制进最终镜像。

## 许可服务

本仓库保留内部 `assets/SolidWorks_Flexnet_Server`，最终镜像默认设置：

```text
START_LOCAL_LICENSE=true
FLEXNET_DIR=/opt/sw-preinstalled/flexnet
```

因此客户端在同一容器中使用本地许可服务。公开 DockerSW 用户仍可通过 `SW_LICENSE_SERVER=25734@host` 连接自己在局域网部署的服务器，或显式挂载并启用本地 `lmgrd`。

## 使用

```bash
docker login "$CI_REGISTRY"
docker run --rm \
  -v "$(pwd):/workspace" \
  "$CI_REGISTRY_IMAGE/sw-preinstalled:latest" \
  sw-export --list list.txt --workspace /workspace --outdir /workspace/dist
```

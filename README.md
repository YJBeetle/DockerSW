# DockerSWPreinstalled

DockerSWPreinstalled 是仅在内网使用的私有构建与部署层。CI 从受控的内网存储下载完整、合法取得的 SOLIDWORKS 安装介质，调用 DockerSW 提供的 `sw-install --accept-eula` 完成 Wine 无头 MSI 安装，然后将成品推送到本项目的 GitLab Container Registry。

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
swloginmgr/SOLIDWORKS Login Manager.msi
```

安装前会导入私有的 `assets/*.reg`。构建中的 `--accept-eula` 表示本仓库的实际维护者已审阅并接受该介质所适用的 EULA；该开关不会授予许可证，也不能替代协议审阅。MSI verbose 日志可能包含序列号，因此成功构建时不会复制进最终镜像；安装失败时只作为保留 1 天的私有 Actions artifact 上传。

## GitHub Actions Google Drive 挂载

`.github/workflows/build-from-google-drive.yml` 提供手动触发的 GitHub Actions 构建。它以只读、无 VFS 磁盘缓存的方式挂载 Google Drive，再对远端 ISO 建立只读 loop mount。安装容器直接 bind mount 已展开的 ISO 文件系统，因此不会下载、解压或复制完整 ISO 到 Docker 构建上下文；实际网络读取量由安装器访问的 ISO 区段决定。

安装期间每 5 分钟输出一次累计耗时、安装容器状态与资源占用、Runner 磁盘空间和最近的 rclone 日志；可通过 `SW_PROGRESS_INTERVAL` 覆盖间隔秒数。

先在 Google Cloud 中为本仓库创建 OAuth Client ID、启用 Google Drive API，然后在本地生成仅供 CI 使用的 `gdrive` remote。应使用自己的 OAuth Client ID，不要依赖 rclone 的共享 Client ID；授权范围选择只读的 `drive.readonly`：

```bash
rclone config
rclone lsf 'gdrive:ISO所在目录'
```

确认能够列出介质后，将该 remote 的完整配置编码为单行：

```bash
rclone config show gdrive | base64 | tr -d '\n'
```

将输出原样保存到 GitHub 私有仓库的 `Settings -> Secrets and variables -> Actions`：

| Secret | 内容 |
|---|---|
| `RCLONE_CONFIG_B64` | 上述命令输出的完整单行 Base64 文本 |

在 Actions 页面手动运行 `Build sw-preinstalled from Google Drive`，必要时覆盖 ISO 在 `gdrive:` remote 中的相对路径。成功后发布私有 GHCR 镜像：

```text
ghcr.io/yjbeetle/sw-preinstalled:latest
ghcr.io/yjbeetle/sw-preinstalled:sha-<仓库提交>
```

流水线只在 Google Drive 配置步骤中读取 Secret，将临时配置文件设为 `0600`，并在结束时删除。它通过临时安装容器和 `docker commit` 固化 Wine prefix，以保留 FUSE/loop mount 的按需读取特性；挂载目录不会进入成品镜像。安装成功时日志会在提交镜像前删除；安装失败时会上传保留 1 天的私有 Actions artifact 供排查。

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

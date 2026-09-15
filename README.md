# DockerSWPreinstalled

DockerSWPreinstalled 是用于构建和发布预装 SOLIDWORKS 的私有镜像仓库。公开的 [DockerSW](https://github.com/YJBeetle/DockerSW) 提供 Wine 运行时、`sw-install` 和 `sw-export`；本仓库负责私有安装配置、本地 FlexNet 服务、完整安装和真实导出验证。

安装介质、序列号、许可证及最终镜像均不得发布到公开仓库或公开镜像包。本仓库及 `ghcr.io/yjbeetle/sw-preinstalled` 应保持私有。

## 构建流程

`.github/workflows/build-from-google-drive.yml` 在影响镜像的内容推送到 `main` 时自动运行，也支持在 Actions 页面手动触发：

1. 根据 DockerSW 子模块提交拉取对应的 `ghcr.io/yjbeetle/sw-runtime:sha-<短 SHA>`。
2. 以只读、无 VFS 磁盘缓存的方式挂载 Google Drive，并对远端 ISO 建立只读 loop mount。
3. 将展开后的 ISO 文件系统直接只读挂载给安装容器，执行 `sw-install --accept-eula`。
4. 将安装结果和本仓库的内部 FlexNet 服务固化为临时镜像；ISO、rclone 配置和安装日志不会进入镜像。
5. 先将不可变的 `sha-<仓库提交>` 候选镜像推送到私有 GHCR，便于失败后在 NAS 上复现和调查。
6. 使用安装后自带的零件、装配体和工程图执行真实 `sw-export`，并检查 6 个 PDF、DWG、STEP 输出均存在且非空。
7. 只有真实导出通过后，才将同一成品镜像推送为 `latest`。

真实导出覆盖以下四个随 SOLIDWORKS 安装的样例：`bezel moldbase.slddrw`、`bezel moldbase.sldasm`、`cabinet_bath.slddrw` 和 `Paper Airplane.SLDPRT`。工程图分别验证 PDF 与 DWG，装配体和零件验证 STEP。

安装期间每 5 分钟输出累计耗时、容器资源占用、Runner 磁盘空间和最近的 rclone 日志。安装失败时，诊断日志会作为私有 Actions artifact 保留 14 天；导出失败时，导出日志和已生成文件同样保留 14 天。导出失败不会覆盖 `latest`，但对应 SHA 候选镜像会保留，便于在 NAS 上继续调查。

## Google Drive 配置

在 Google Cloud 中创建 OAuth Client ID、启用 Google Drive API，并将 OAuth 应用发布为正式版。建议使用自己的 Client ID、只读 `drive.readonly` 权限，并在本地生成专供 CI 使用的 `gdrive` remote：

```bash
rclone config
rclone lsf 'gdrive:ISO所在目录'
```

确认能够列出介质后，将该 remote 的完整配置编码为单行：

```bash
rclone config show gdrive | base64 | tr -d '\n'
```

将输出保存为 GitHub 仓库的 Actions Secret：

| Secret | 内容 |
|---|---|
| `RCLONE_CONFIG_B64` | `gdrive` remote 完整配置的单行 Base64 文本 |

默认介质路径为：

```text
Share/Software/DS.SolidWorks.2025.SP5.0.Premium-SSQ/SolidWorks.2025.SP5.0.Premium.DVD.iso
```

手动运行 `Build sw-preinstalled from Google Drive` 时可以覆盖该路径。工作流使用 `--vfs-cache-mode off --buffer-size 0`，不会把整个 ISO 缓存到 Runner；安装器读取哪些 ISO 区段，rclone 才从远端读取相应数据。

`.github/workflows/check-google-drive.yml` 每两个月及手动触发时执行一次轻量目录读取，用于验证 Secret、OAuth refresh token 和目标文件仍然可访问。

## EULA 与安装输入

构建中的 `--accept-eula` 表示本仓库维护者已审阅并接受安装介质所适用的 EULA。该参数不会授予软件许可证，也不能替代协议审阅。

安装完成后，`assets/SOLIDWORKS Corp/SOLIDWORKS/` 的内容会覆盖到实际的 Wine SOLIDWORKS 程序目录。当前官方 MSI 的实际目录是 `drive_c/Program Files/SOLIDWORKS`，安装器保留的 `SOLIDWORKS Corp/SOLIDWORKS` 兼容路径会自动解析到同一位置。

安装前会导入 `assets/*.reg` 中的私有安装配置，并从 `assets/SolidWorks_Flexnet_Server` 装入内部许可服务。最终镜像默认使用：

```text
START_LOCAL_LICENSE=true
FLEXNET_DIR=/opt/sw-preinstalled/flexnet
```

## 手动触发

可以在 GitHub 的 `Actions` 页面选择 `Build sw-preinstalled from Google Drive`，点击 `Run workflow`；也可以使用 GitHub CLI：

```bash
gh workflow run build-from-google-drive.yml \
  --repo YJBeetle/DockerSWPreinstalled \
  --ref main
```

## 使用

先让 GitHub PAT 具备读取私有 package 的权限，再登录 GHCR：

```bash
printf '%s' "$GHCR_TOKEN" | docker login ghcr.io -u YJBeetle --password-stdin

docker run --rm \
  -v "$(pwd):/workspace" \
  ghcr.io/yjbeetle/sw-preinstalled:latest \
  sw-export --list list.txt --workspace /workspace --outdir /workspace/dist
```

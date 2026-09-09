# DockerSWComplete

完整的 SolidWorks 2025 一体化无头容器（含内置 FlexNet 本地授权守护服务、Wine 运行栈、COM 批量静默导出 CLI 工具）。

## 架构特性

- **开箱即用（Zero-Mount）**：SolidWorks 二进制程序、注册表、运行库、License 全部内置于镜像中。
- **自动授权**：容器启动时后台自动拉起轻量级 FlexNet 守护服务，无需外部授权服务器。
- **自动化 CI 流水线**：推送分支或打 Tag 时，通过 GitLab CI 自动构建并发布至 Docker Hub。

## 环境变量配置 (GitLab CI/CD Variables)

在 GitLab 项目设置中 (`Settings` -> `CI/CD` -> `Variables`) 添加以下变量：

| 变量名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `DOCKERHUB_USERNAME` | Variable | Docker Hub 注册用户名 |
| `DOCKERHUB_PASSWORD` | Masked Variable | Docker Hub 访问令牌 (Personal Access Token) 或密码 |
| `DOCKERHUB_IMAGE` | Variable (可选) | 目标镜像仓库名，默认为 `yjbeetle/dockersw-complete` |

## 快速使用

```bash
docker run --rm \
  -v $(pwd):/workspace \
  yjbeetle/dockersw-complete:latest \
  dockersw-export --list list.txt --workspace /workspace --outdir /workspace/dist
```

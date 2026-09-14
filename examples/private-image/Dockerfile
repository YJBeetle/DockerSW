# syntax=docker/dockerfile:1.7

# 企业私有仓库示例：从公开运行时和合法取得的完整介质构建预安装镜像。
# 构建上下文需要提供 private-media/SOLIDWORKS.iso，但不得将其提交到公开仓库。
ARG BASE_IMAGE=ghcr.io/yjbeetle/sw-runtime:latest
FROM ${BASE_IMAGE}

# --accept-eula 表示执行构建的个人或组织已阅读并接受适用于该介质的 EULA。
# BuildKit bind mount 不会把 ISO COPY 到最终镜像层；构建仍应只在可信私有环境中进行。
RUN --mount=type=bind,source=private-media/SOLIDWORKS.iso,target=/tmp/SOLIDWORKS.iso,ro \
    sw-install --media /tmp/SOLIDWORKS.iso --accept-eula \
    && rm -rf /var/log/sw-install

# 推荐在运行时通过 SW_LICENSE_SERVER 注入局域网许可服务器地址。
# 如需本地 lmgrd，可挂载 /opt/SolidWorks_Flexnet_Server 并设置 START_LOCAL_LICENSE=true。
WORKDIR /workspace

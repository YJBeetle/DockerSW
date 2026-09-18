# DockerSW: SolidWorks 本地可执行镜像 (注入内部许可服务供离线/交叉冒烟测试)
ARG BASE_IMAGE=ghcr.io/yjbeetle/sw-preinstalled:latest
FROM ${BASE_IMAGE}

LABEL maintainer="YJBeetle"
LABEL description="Private SolidWorks headless executable container with internal FlexNet service"

# 1. 注入测试用内部 FlexNet 许可服务端
COPY ["assets/SolidWorks_Flexnet_Server/", "/opt/sw-flexnet/"]

# 2. 覆盖 SOLIDWORKS 程序补丁
COPY ["assets/SOLIDWORKS Corp/SOLIDWORKS/", "/root/.wine/drive_c/Program Files/SOLIDWORKS/"]

# 3. 导入测试网络序列号与许可注册表
RUN --mount=type=bind,source=assets,target=/mnt/assets \
    find /mnt/assets -maxdepth 1 -iname '*serials_licensing.reg' -exec wine regedit /S {} + && \
    wineserver -w

# 4. 配置许可服务
ENV SW_FLEXNET_DIR=/opt/sw-flexnet
ENV SW_LICENSE_SERVER=

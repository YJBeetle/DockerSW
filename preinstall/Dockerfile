# DockerSW: SolidWorks 官方原版静默预装镜像
# 在 sw-runtime 基础上挂载官方安装介质执行无人值守安装，生成 100% 纯净的原版预装镜像
ARG BASE_IMAGE=ghcr.io/yjbeetle/sw-runtime:latest
FROM ${BASE_IMAGE}

LABEL maintainer="YJBeetle"
LABEL description="Private SolidWorks headless container with official installation"

# 挂载官方安装介质并执行无人值守静默安装
RUN --mount=type=bind,source=media,target=/mnt/sw-media \
    sw-install \
        --media /mnt/sw-media \
        --accept-eula \
        --log-dir /var/log/sw-install && \
    sw_program_dir="/root/.wine/drive_c/Program Files/SOLIDWORKS" && \
    test -d "${sw_program_dir}" && \
    test -f "${sw_program_dir}/SLDWORKS.exe" && \
    rm -rf /var/log/sw-install

ENV START_LOCAL_LICENSE=false
ENV SW_LICENSE_SERVER=

WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["sw-export", "--help"]

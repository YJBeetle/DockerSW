# DockerSWPreinstalled: 从私有介质执行官方 MSI 安装，并内置内部 FlexNet 服务。
ARG BASE_IMAGE
FROM ${BASE_IMAGE} AS solidworks-installer

LABEL maintainer="YJBeetle"
LABEL description="Private SolidWorks headless CI container built from official installation media"

# 安装介质由私有 GitLab CI 下载到固定路径，不存在于 Git 仓库中。
COPY .ci-media/solidworks-media /opt/dockersw/private-media/solidworks-media
COPY assets/solidworks_reg /opt/dockersw/private-registry

ARG SW_INSTALL_TIMEOUT=10800
RUN SW_INSTALL_TIMEOUT="${SW_INSTALL_TIMEOUT}" \
    dockersw-install \
      --media /opt/dockersw/private-media/solidworks-media \
      --registry-dir /opt/dockersw/private-registry \
      --log-dir /var/log/dockersw-install && \
    rm -rf /opt/dockersw/private-media /opt/dockersw/private-registry

FROM ${BASE_IMAGE}

LABEL maintainer="YJBeetle"
LABEL description="Private SolidWorks headless CI container with an internal FlexNet service"

# 最终镜像只复制安装后的 Wine prefix，不包含原始 ISO/压缩包或安装日志。
COPY --from=solidworks-installer /root/.wine /root/.wine
COPY assets/SolidWorks_Flexnet_Server /opt/SolidWorks_Flexnet_Server

ENV START_LOCAL_LICENSE=true
ENV FLEXNET_DIR=/opt/SolidWorks_Flexnet_Server
ENV SW_LICENSE_SERVER=

RUN test -f "/root/.wine/drive_c/Program Files/SOLIDWORKS Corp/SOLIDWORKS/SLDWORKS.exe" && \
    test -f "/opt/SolidWorks_Flexnet_Server/lmgrd.exe"

WORKDIR /workspace

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["dockersw-export", "--help"]

# DockerSWPreinstalled: 从私有介质执行官方 MSI 安装，并内置内部 FlexNet 服务。
ARG BASE_IMAGE
FROM ${BASE_IMAGE} AS solidworks-installer

LABEL maintainer="YJBeetle"
LABEL description="Private SolidWorks headless CI container built from official installation media"

# 安装介质由私有 GitLab CI 下载到固定路径，不存在于 Git 仓库中。
COPY .ci-media/solidworks-media /opt/sw-preinstalled/private-media/solidworks-media
COPY assets/*.reg /opt/sw-preinstalled/private-registry/

ARG SW_INSTALL_TIMEOUT=10800
RUN SW_INSTALL_TIMEOUT="${SW_INSTALL_TIMEOUT}" \
    sw-install \
      --media /opt/sw-preinstalled/private-media/solidworks-media \
      --registry-dir /opt/sw-preinstalled/private-registry \
      --accept-eula \
      --log-dir /var/log/sw-install && \
    rm -rf /opt/sw-preinstalled/private-media /opt/sw-preinstalled/private-registry

FROM ${BASE_IMAGE}

LABEL maintainer="YJBeetle"
LABEL description="Private SolidWorks headless CI container with an internal FlexNet service"

# 最终镜像只复制安装后的 Wine prefix，不包含原始 ISO/压缩包或安装日志。
COPY --from=solidworks-installer /root/.wine /root/.wine
COPY assets/SolidWorks_Flexnet_Server /opt/sw-preinstalled/flexnet

ENV START_LOCAL_LICENSE=true
ENV FLEXNET_DIR=/opt/sw-preinstalled/flexnet
ENV SW_LICENSE_SERVER=

RUN test -f "/root/.wine/drive_c/Program Files/SOLIDWORKS Corp/SOLIDWORKS/SLDWORKS.exe" && \
    test -f "/opt/sw-preinstalled/flexnet/lmgrd.exe"

WORKDIR /workspace

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["sw-export", "--help"]

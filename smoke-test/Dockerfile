# DockerSW: SolidWorks 本地可执行镜像 (注入内部许可服务供离线/交叉冒烟测试)
ARG BASE_IMAGE=sw-preinstalled-base:local
ARG APP_IMAGE=sw-runtime:local

FROM ${APP_IMAGE} AS current-app
FROM ${BASE_IMAGE} AS sw-executable-base

LABEL maintainer="YJBeetle"
LABEL description="Private SolidWorks headless executable container with internal FlexNet service"

# 1. 注入测试用内部 FlexNet 许可服务端
COPY ["smoke-test/assets/SolidWorks_Flexnet_Server/", "/opt/sw-flexnet/"]

# 2. 覆盖 SOLIDWORKS 程序补丁
COPY ["smoke-test/assets/SOLIDWORKS Corp/SOLIDWORKS/", "/root/.wine/drive_c/Program Files/SOLIDWORKS/"]

# 3. 导入测试网络序列号与许可注册表
RUN --mount=type=bind,source=smoke-test/assets,target=/mnt/assets \
    find /mnt/assets -maxdepth 1 -iname '*serials_licensing.reg' -exec wine regedit /S {} + && \
    wineserver -w

# 4. 配置许可服务
ENV SW_FLEXNET_DIR=/opt/sw-flexnet
ENV SW_LICENSE_SERVER=


FROM sw-executable-base AS sw-executable

COPY --from=current-app /opt/swcli/ /opt/swcli/
COPY --from=current-app /usr/local/lib/sw-runtime/install_swcli.sh /usr/local/lib/sw-runtime/install_swcli.sh
COPY --from=current-app /usr/local/bin/sw-install /usr/local/bin/sw-install
COPY --from=current-app /usr/local/bin/sw-cli /usr/local/bin/sw-cli
COPY --from=current-app /usr/local/bin/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN /usr/local/lib/sw-runtime/install_swcli.sh /opt/swcli

WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/bin/bash"]

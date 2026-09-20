# DockerSW: SolidWorks 官方原版静默预装镜像
# 在 sw-runtime 基础上挂载官方安装介质执行无人值守安装，生成 100% 纯净的原版预装镜像
ARG BASE_IMAGE=sw-runtime-base:local
ARG APP_IMAGE=sw-runtime:local

FROM ${APP_IMAGE} AS current-app
FROM ${BASE_IMAGE} AS sw-preinstalled-base

LABEL maintainer="YJBeetle"
LABEL description="Private SolidWorks headless container with official installation"

# 接收官方安装所需的序列号与许可配置（构建参数不持久化到最终镜像 ENV 中）
ARG SW_SERIAL_SOLIDWORKS=""
ARG SW_SERIAL_SIMULATION=""
ARG SW_SERIAL_MOTION=""
ARG SW_SERIAL_MBD=""
ARG SW_LICENSE_SERVER=""

# 挂载官方安装介质并执行无人值守静默安装（纯参数传递，零注册表侵入）
RUN --mount=type=bind,source=preinstall/media,target=/mnt/sw-media \
    SW_SERIAL_SOLIDWORKS="${SW_SERIAL_SOLIDWORKS}" \
    SW_SERIAL_SIMULATION="${SW_SERIAL_SIMULATION}" \
    SW_SERIAL_MOTION="${SW_SERIAL_MOTION}" \
    SW_SERIAL_MBD="${SW_SERIAL_MBD}" \
    SW_LICENSE_SERVER="${SW_LICENSE_SERVER}" \
    sw-install \
        --media /mnt/sw-media \
        --accept-eula \
        --log-dir /var/log/sw-install && \
    sw_program_dir="/root/.wine/drive_c/Program Files/SOLIDWORKS" && \
    test -d "${sw_program_dir}" && \
    test -f "${sw_program_dir}/SLDWORKS.exe" && \
    rm -rf /var/log/sw-install

ENV SW_LICENSE_SERVER=


FROM sw-preinstalled-base AS sw-preinstalled

# 从同一次构建的 sw-runtime 复制当前应用层，并在已经安装 SOLIDWORKS 的
# Wine prefix 中安装完全相同的 SWCLI。基础安装层因此不随 CLI 改动失效。
COPY --from=current-app /opt/swcli/ /opt/swcli/
COPY --from=current-app /usr/local/lib/sw-runtime/install_swcli.sh /usr/local/lib/sw-runtime/install_swcli.sh
COPY --from=current-app /usr/local/bin/sw-install /usr/local/bin/sw-install
COPY --from=current-app /usr/local/bin/sw-cli /usr/local/bin/sw-cli
COPY --from=current-app /usr/local/bin/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN /usr/local/lib/sw-runtime/install_swcli.sh /opt/swcli

WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/bin/bash"]

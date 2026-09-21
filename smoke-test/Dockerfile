# DockerSW: 在稳定的测试运行基础层上加入当前 SWCLI
ARG BASE_IMAGE=sw-executable-base:local
ARG APP_IMAGE=sw-runtime:local

FROM ${APP_IMAGE} AS current-app
FROM ${BASE_IMAGE} AS sw-executable

# 交付层不接触 FlexNet、授权注册表或 SOLIDWORKS 程序补丁。
# --link 使它与 preinstalled 及各语言交付镜像复用同一 payload 层。
COPY --link --from=current-app /opt/swcli/ /opt/swcli/
COPY --link --from=current-app /usr/local/bin/sw-cli /usr/local/bin/sw-cli
COPY --link --from=current-app /usr/local/bin/linux-to-wine-path /usr/local/bin/linux-to-wine-path
COPY --link --from=current-app /usr/local/bin/entrypoint.sh /usr/local/bin/entrypoint.sh

WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/bin/bash"]

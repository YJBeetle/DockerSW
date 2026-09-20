# DockerSW: 在稳定的测试运行基础层上加入当前 SWCLI
ARG BASE_IMAGE=sw-executable-base:local
ARG APP_IMAGE=sw-runtime:local

FROM ${APP_IMAGE} AS current-app
FROM ${BASE_IMAGE} AS sw-executable

# 交付层不接触 FlexNet、授权注册表或 SOLIDWORKS 程序补丁。
COPY --from=current-app /opt/swcli/ /opt/swcli/
COPY --from=current-app /usr/local/lib/sw-runtime/install_swcli.sh /usr/local/lib/sw-runtime/install_swcli.sh
COPY --from=current-app /usr/local/bin/sw-install /usr/local/bin/sw-install
COPY --from=current-app /usr/local/bin/sw-cli /usr/local/bin/sw-cli
COPY --from=current-app /usr/local/bin/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN /usr/local/lib/sw-runtime/install_swcli.sh /opt/swcli

WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/bin/bash"]

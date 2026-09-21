# DockerSW: 在已安装 SOLIDWORKS 的稳定基础层上加入当前 SWCLI
ARG BASE_IMAGE=sw-preinstalled-base:local
ARG APP_IMAGE=sw-runtime:local

FROM ${APP_IMAGE} AS current-app
FROM ${BASE_IMAGE} AS sw-preinstalled

# 交付层不接触安装介质。--link 让相同 SWCLI payload 不依赖不同的
# SOLIDWORKS/语言父层，所有交付变体可引用相同的内容层。
COPY --link --from=current-app /opt/swcli/ /opt/swcli/
COPY --link --from=current-app /usr/local/bin/sw-cli /usr/local/bin/sw-cli
COPY --link --from=current-app /usr/local/bin/linux-to-wine-path /usr/local/bin/linux-to-wine-path
COPY --link --from=current-app /usr/local/bin/entrypoint.sh /usr/local/bin/entrypoint.sh

WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/bin/bash"]

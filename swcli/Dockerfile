# DockerSW: 当前 SWCLI 与容器适配器组成的内部应用载荷
FROM scratch AS swcli-payload

COPY --link swcli/SWCLI/ /opt/swcli/
COPY --link --chmod=755 \
    runtime/bin/sw-cli \
    runtime/bin/linux-to-wine-path \
    /usr/local/bin/
COPY --link --chmod=755 swcli/entrypoint-cli.sh /usr/local/bin/entrypoint-cli.sh

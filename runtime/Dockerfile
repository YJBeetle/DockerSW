# DockerSW: 在稳定 Wine 基础层上加入当前 SWCLI 与容器入口
ARG BASE_IMAGE=sw-runtime-base:local
FROM ${BASE_IMAGE} AS sw-runtime

# 1. 三个正式镜像共享的当前应用层。Linux 与 Wine Windows Python 都直接
# 从 /opt/swcli/src 运行；SWCLI 不写入 Wine prefix。
COPY --link SWCLI/ /opt/swcli/

# 2. 加入与 SWCLI 配套的 Docker/Wine 进程与路径适配器。
# sw-install 已属于稳定的 sw-runtime-base，不在交付层重复复制。
COPY --link --chmod=755 \
    runtime/bin/sw-cli \
    runtime/bin/linux-to-wine-path \
    /usr/local/bin/

# 3. 配置容器 Entrypoint
COPY --link --chmod=755 runtime/entrypoint.sh /usr/local/bin/entrypoint.sh

WORKDIR /workspace

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/bin/bash"]

# DockerSW: 无头 SolidWorks Wine 运行与 CI 导出基础镜像
FROM ubuntu:22.04 AS sw-runtime-base

LABEL maintainer="YJBeetle"
LABEL description="Headless Wine container for SolidWorks automated CI export (STEP/PDF/DWG/GLB) & VNC GUI"

ENV DEBIAN_FRONTEND=noninteractive
ENV WINEARCH=win64
ENV WINEPREFIX=/root/.wine
ENV WINEDEBUG=-all
ENV DISPLAY=:99
ENV PYTHON_VERSION=3.11.9
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# 1. 配置系统基础依赖与 WineHQ 仓库。
# jq 是有意内置的运行时工具，方便下游在容器内直接 `sw-cli --json | jq` 处理结构化输出。
RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        jq \
        wget \
        gnupg \
        xvfb \
        openbox \
        x11vnc \
        libgl1-mesa-dri \
        mesa-utils \
        cabextract \
        msitools \
        p7zip-full \
        zstd \
        procps \
        fonts-noto-cjk \
        fonts-wqy-microhei \
        locales && \
    mkdir -pm755 /etc/apt/keyrings && \
    wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key && \
    wget -O /etc/apt/sources.list.d/winehq-jammy.sources https://dl.winehq.org/wine-builds/ubuntu/dists/jammy/winehq-jammy.sources && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 2. 复制运行时需要的组件与配置
# 与 MacSW 已验证环境保持 Wine 11.16 / Wine-Mono 11.3.0 一致，但不引入
# 仅适用于 macOS 的 winemac/win32u 补丁。
COPY runtime/managed_com.env /opt/sw-runtime/managed_com.env
COPY --chmod=755 runtime/prepare_managed_com.sh /usr/local/lib/sw-runtime/prepare_managed_com.sh
COPY --chmod=755 runtime/patch_win32u.pl /usr/local/lib/sw-runtime/patch_win32u.pl
COPY --chmod=755 runtime/patch_wine_mono.pl /usr/local/lib/sw-runtime/patch_wine_mono.pl


# 3. 安装 Wine、下载 Mono 资产并初始化无头运行环境（合并在单层内执行反向去重，消除 540MB 重复物理占用）
# 仅绑定挂载本层真正消费的三个源（两个构建脚本 + registry 目录），避免把整个
# runtime/ 树纳入缓存键——否则 runtime/bin、runtime/scripts、runtime/tests 的
# 任何改动都会击穿这一层，导致约 145s 的 Wine/Mono/Python 安装被无谓重建。
RUN --mount=type=bind,source=runtime/fetch_managed_com.sh,target=/mnt/runtime/fetch_managed_com.sh \
    --mount=type=bind,source=runtime/init_wineprefix.sh,target=/mnt/runtime/init_wineprefix.sh \
    --mount=type=bind,source=runtime/registry,target=/mnt/runtime/registry \
    . /opt/sw-runtime/managed_com.env && \
    apt-get update && \
    apt-get install -y --install-recommends \
        "wine-devel-amd64=${WINE_PACKAGE_VERSION}" \
        "wine-devel-i386:i386=${WINE_PACKAGE_VERSION}" \
        "wine-devel=${WINE_PACKAGE_VERSION}" \
        "winehq-devel=${WINE_PACKAGE_VERSION}" && \
    test "$(wine --version)" = "wine-${WINE_VERSION}" && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    bash /mnt/runtime/fetch_managed_com.sh && \
    wget -q "https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-amd64.exe" -O /tmp/python-installer.exe && \
    bash /mnt/runtime/init_wineprefix.sh && \
    rm -rf /tmp/* /root/.cache/*

# 4. 仅加入执行 SOLIDWORKS 官方安装所需的稳定工具。频繁变化的 SWCLI、
# DockerSW 运行脚本与入口点留到各正式镜像的最后一层。
COPY --chmod=755 runtime/bin/sw-install /usr/local/bin/sw-install

WORKDIR /workspace


FROM sw-runtime-base AS sw-runtime

# 5. 三个正式镜像共享的当前应用层。Linux 与 Wine Windows Python 都直接
# 从 /opt/swcli/src 运行；SWCLI 不写入 Wine prefix。
COPY --link SWCLI/ /opt/swcli/

# 6. 安装 DockerSW 的进程/路径适配器
COPY --link --chmod=755 runtime/bin/ /usr/local/bin/

# 7. 配置容器 Entrypoint
COPY --link --chmod=755 runtime/entrypoint.sh /usr/local/bin/entrypoint.sh

WORKDIR /workspace

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/bin/bash"]

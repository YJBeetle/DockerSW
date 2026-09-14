# DockerSW: 无头 SolidWorks Wine 运行与 CI 导出基础镜像
FROM ubuntu:22.04

LABEL maintainer="YJBeetle"
LABEL description="Headless Wine container for SolidWorks automated CI export (STEP/PDF/DWG/GLB)"

ENV DEBIAN_FRONTEND=noninteractive
ENV WINEARCH=win64
ENV WINEPREFIX=/root/.wine
ENV WINEDEBUG=-all
ENV DISPLAY=:99
ENV PYTHON_VERSION=3.11.9
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# 1. 配置系统基础依赖与 WineHQ 仓库。
RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        wget \
        gnupg \
        xvfb \
        cabextract \
        p7zip-full \
        zstd \
        procps \
        fonts-noto-cjk \
        fonts-wqy-microhei \
        locales && \
    mkdir -pm755 /etc/apt/keyrings && \
    wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key && \
    wget -O /etc/apt/sources.list.d/winehq-jammy.sources https://dl.winehq.org/wine-builds/ubuntu/dists/jammy/winehq-jammy.sources

# 与 WineSW 已验证环境保持 Wine 11.16 / Wine-Mono 11.3.0 一致，但不引入
# 仅适用于 macOS 的 winemac/win32u 补丁。
COPY docker/managed_com.env /opt/dockersw/managed_com.env
RUN . /opt/dockersw/managed_com.env && \
    apt-get update && \
    apt-get install -y --install-recommends \
        "wine-devel-amd64=${WINE_PACKAGE_VERSION}" \
        "wine-devel-i386:i386=${WINE_PACKAGE_VERSION}" \
        "wine-devel=${WINE_PACKAGE_VERSION}" \
        "winehq-devel=${WINE_PACKAGE_VERSION}" && \
    test "$(wine --version)" = "wine-${WINE_VERSION}" && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 2. 下载 Windows Python、Wine-Mono 以及已验证的 stdcall/COM 注册组件。
# 所有外部二进制均固定版本并执行 SHA256 校验，不提交到公开仓库。
COPY docker/fetch_managed_com.sh /tmp/fetch_managed_com.sh
RUN wget -q "https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-amd64.exe" -O /tmp/python-installer.exe && \
    chmod +x /tmp/fetch_managed_com.sh && \
    /tmp/fetch_managed_com.sh && \
    rm -f /tmp/fetch_managed_com.sh

# 3. 复制注册表配置与初始化脚本
COPY docker/registry/headless_tweaks.reg /tmp/headless_tweaks.reg
COPY docker/registry/license_template.reg /tmp/license_template.reg
COPY docker/registry/sw_com_classes.reg /tmp/sw_com_classes.reg
COPY docker/init_wineprefix.sh /tmp/init_wineprefix.sh
COPY docker/prepare_managed_com.sh /usr/local/lib/dockersw/prepare_managed_com.sh

# 4. 执行 WinePrefix 初始化（先创建干净 prefix，再显式安装并修补 Mono、Python 与 pywin32）
RUN chmod +x /tmp/init_wineprefix.sh /usr/local/lib/dockersw/prepare_managed_com.sh && \
    /tmp/init_wineprefix.sh && \
    rm -rf /tmp/*

# 5. 安装核心导出脚本、全局 CLI 命令与内置注册表
RUN mkdir -p /opt/dockersw/scripts /opt/dockersw/registry
COPY scripts/export_sw.py /opt/dockersw/scripts/export_sw.py
COPY docker/registry/sw_com_classes.reg /opt/dockersw/registry/sw_com_classes.reg
COPY scripts/sw-export /usr/local/bin/sw-export
COPY scripts/install_solidworks.sh /usr/local/bin/sw-install
RUN chmod +x /usr/local/bin/sw-export /usr/local/bin/sw-install

# 6. 配置容器 Entrypoint
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /workspace

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/usr/local/bin/sw-export", "--help"]

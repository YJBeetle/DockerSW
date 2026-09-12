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

# 1. 配置系统基础依赖与 WineHQ 仓库
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
    wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/jammy/winehq-jammy.sources && \
    apt-get update && \
    apt-get install -y --install-recommends wine-stable-amd64 wine-stable-i386 winehq-stable && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 2. 下载 Windows Python 官方安装包与 Wine-Mono 官方运行时。
# Wine-Mono MSI 必须避开 Wine 的自动发现目录，等 wineboot 完成后再显式安装。
RUN wget -q "https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-amd64.exe" -O /tmp/python-installer.exe && \
    mkdir -p /opt/dockersw/cache && \
    wget -q "https://dl.winehq.org/wine/wine-mono/11.0.0/wine-mono-11.0.0-x86.msi" -O /opt/dockersw/cache/wine-mono-11.0.0-x86.msi

# 3. 复制注册表配置与初始化脚本
COPY docker/registry/headless_tweaks.reg /tmp/headless_tweaks.reg
COPY docker/registry/license_template.reg /tmp/license_template.reg
COPY docker/registry/sw_com_classes.reg /tmp/sw_com_classes.reg
COPY docker/init_wineprefix.sh /tmp/init_wineprefix.sh

# 4. 执行 WinePrefix 初始化（先创建干净 prefix，再显式安装 Mono、Python 与 pywin32）
RUN chmod +x /tmp/init_wineprefix.sh && \
    /tmp/init_wineprefix.sh && \
    rm -rf /tmp/*

# 5. 安装核心导出脚本、全局 CLI 命令与内置注册表
RUN mkdir -p /opt/dockersw/scripts /opt/dockersw/registry
COPY scripts/export_sw.py /opt/dockersw/scripts/export_sw.py
COPY docker/registry/sw_com_classes.reg /opt/dockersw/registry/sw_com_classes.reg
COPY scripts/dockersw-export /usr/local/bin/dockersw-export
COPY scripts/install_solidworks.sh /usr/local/bin/dockersw-install
RUN chmod +x /usr/local/bin/dockersw-export /usr/local/bin/dockersw-install

# 6. 配置容器 Entrypoint
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /workspace

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/usr/local/bin/dockersw-export", "--help"]

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
        procps \
        fonts-noto-cjk \
        fonts-wqy-microhei \
        locales && \
    mkdir -pm755 /etc/apt/keyrings && \
    wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key && \
    wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/jammy/winehq-jammy.sources && \
    apt-get update && \
    apt-get install -y --install-recommends winehq-stable && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 2. 下载 Windows Python 官方安装包并初始化 Wine 环境
RUN wget -q "https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-amd64.exe" -O /tmp/python-installer.exe

# 3. 复制注册表配置与初始化脚本
COPY docker/registry/headless_tweaks.reg /tmp/headless_tweaks.reg
COPY docker/registry/license_template.reg /tmp/license_template.reg
COPY docker/init_wineprefix.sh /tmp/init_wineprefix.sh

# 4. 执行 WinePrefix 初始化（安装 Windows Python + pywin32 + 导入注册表）
RUN chmod +x /tmp/init_wineprefix.sh && \
    /tmp/init_wineprefix.sh && \
    rm -rf /tmp/*

# 5. 安装核心导出脚本与全局 CLI 命令
RUN mkdir -p /opt/dockersw/scripts
COPY scripts/export_sw.py /opt/dockersw/scripts/export_sw.py
COPY scripts/dockersw-export /usr/local/bin/dockersw-export
RUN chmod +x /usr/local/bin/dockersw-export

# 6. 配置容器 Entrypoint
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /workspace

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/usr/local/bin/dockersw-export", "--help"]

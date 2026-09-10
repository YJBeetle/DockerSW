# DockerSWComplete: 完整内置 SolidWorks 2025 二进制与 FlexNet 本地授权服务的一体化无头 CI 容器
ARG BASE_IMAGE=ghcr.io/yjbeetle/dockersw:latest
FROM ${BASE_IMAGE}

LABEL maintainer="YJBeetle"
LABEL description="All-in-One SolidWorks 2025 Headless CI Container with Built-in Activation & Export CLI"

# 1. 注入核心导出脚本、CLI 命令与入口配置（源自 submodule DockerSW）
COPY DockerSW/scripts/export_sw.py /opt/dockersw/scripts/export_sw.py
COPY DockerSW/scripts/dockersw-export /usr/local/bin/dockersw-export
RUN chmod +x /usr/local/bin/dockersw-export

COPY DockerSW/docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# 2. 复制 SolidWorks 完整程序包、激活服务、依赖 DLL 与注册表
COPY ["assets/SOLIDWORKS", "/opt/solidworks/"]
COPY assets/SolidWorks_Flexnet_Server /opt/SolidWorks_Flexnet_Server
COPY assets/solidworks_reg /opt/solidworks_reg
COPY assets/vc_redist_dlls /opt/vc_redist_dlls
COPY assets/wine-mono-11.0.0-x86.msi /opt/wine-mono.msi

# 3. 预热与持久化：在构建期静默安装 Mono、注入 DLL、映射程序、导入注册表
ENV START_LOCAL_LICENSE=true
RUN /usr/local/bin/entrypoint.sh --init-only && rm -rf /tmp/.X11-unix /tmp/*

WORKDIR /workspace

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["dockersw-export", "--help"]

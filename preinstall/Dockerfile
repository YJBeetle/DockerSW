# DockerSW: SolidWorks 官方原版静默预装镜像
# 在 sw-runtime 上挂载官方安装介质，生成不含 SWCLI 的稳定安装层
ARG RUNTIME_IMAGE=sw-runtime:local
FROM ${RUNTIME_IMAGE} AS sw-preinstalled

LABEL maintainer="YJBeetle"
LABEL description="Private SolidWorks headless container with official installation"

# 接收官方安装所需的序列号与许可配置（构建参数不持久化到最终镜像 ENV 中）
ARG SW_SERIAL_SOLIDWORKS=""
ARG SW_SERIAL_SIMULATION=""
ARG SW_SERIAL_MOTION=""
ARG SW_SERIAL_MBD=""
ARG SW_LICENSE_SERVER=""

# 只向 BuildKit 传入安装流程已在真实 MSI 安装中验证过的官方目录。
# Toolbox 是核心 MSI InstallFinalize 的必需输入；dotNetFx 用于补齐 Wine WPF 主题。
RUN --mount=type=bind,from=sw-data,target=/mnt/sw-media/swwi/data \
    --mount=type=bind,from=sw-toolbox,target=/mnt/sw-media/Toolbox \
    --mount=type=bind,from=sw-login,target=/mnt/sw-media/swloginmgr \
    --mount=type=bind,from=sw-vcredist,target=/mnt/sw-media/PreReqs/VCRedist17 \
    --mount=type=bind,from=sw-dotnet,target=/mnt/sw-media/PreReqs/dotNetFx \
    SW_SERIAL_SOLIDWORKS="${SW_SERIAL_SOLIDWORKS}" \
    SW_SERIAL_SIMULATION="${SW_SERIAL_SIMULATION}" \
    SW_SERIAL_MOTION="${SW_SERIAL_MOTION}" \
    SW_SERIAL_MBD="${SW_SERIAL_MBD}" \
    SW_LICENSE_SERVER="${SW_LICENSE_SERVER}" \
    sw-install \
        --media /mnt/sw-media \
        --accept-eula \
        --log-dir /var/log/sw-install && \
    sw_program_dir="/root/.wine/drive_c/Program Files/SOLIDWORKS" && \
    test -d "${sw_program_dir}" && \
    test -f "${sw_program_dir}/SLDWORKS.exe" && \
    rm -rf /var/log/sw-install

ENV SW_LICENSE_SERVER=

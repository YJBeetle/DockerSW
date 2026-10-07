# DockerSW: SolidWorks 官方原版静默预装镜像
# 在 sw-runtime 上挂载官方安装介质，生成不含 SWCLI 的稳定安装层
ARG RUNTIME_IMAGE=sw-runtime:local
FROM ${RUNTIME_IMAGE} AS sw-preinstalled

LABEL maintainer="YJBeetle"
LABEL description="Private SolidWorks headless container with official installation"

# 接收官方安装所需的序列号与许可配置（构建参数不持久化到最终镜像 ENV 中）
ARG SW_SERIAL_SOLIDWORKS=""
ARG SW_LICENSE_SERVER=""

# 只向 BuildKit 传入安装阶段所需的官方目录。
# Toolbox 是核心 MSI InstallFinalize 的必需输入；VBA 保留完整官方 MSI/CAB
# 目录并在主程序前安装；dotNetFx 用于补齐 Wine WPF 主题。
RUN --mount=type=bind,from=sw-data,target=/mnt/sw-media/swwi/data \
    --mount=type=bind,from=sw-toolbox,target=/mnt/sw-media/Toolbox \
    --mount=type=bind,from=sw-login,target=/mnt/sw-media/swloginmgr \
    --mount=type=bind,from=sw-vcredist,target=/mnt/sw-media/PreReqs/VCRedist17 \
    --mount=type=bind,from=sw-vba,target=/mnt/sw-media/PreReqs/VBA,ro \
    --mount=type=bind,from=sw-dotnet,target=/mnt/sw-media/PreReqs/dotNetFx \
    SW_SERIAL_SOLIDWORKS="${SW_SERIAL_SOLIDWORKS}" \
    SW_LICENSE_SERVER="${SW_LICENSE_SERVER}" \
    sw-install \
        --media /mnt/sw-media \
        --log-dir /var/log/sw-install && \
    sw_program_dir="/root/.wine/drive_c/Program Files/SOLIDWORKS" && \
    test -d "${sw_program_dir}" && \
    test -f "${sw_program_dir}/SLDWORKS.exe" && \
    rm -rf /var/log/sw-install

# SOLIDWORKS 模板与资源直接引用的基础字体属于预安装环境，所有语言层和
# 后续可执行镜像均从这里继承。安装脚本与清单只在构建时挂载，不进入镜像。
RUN --mount=type=bind,source=preinstall/install-fonts.sh,target=/mnt/install-fonts.sh,ro \
    --mount=type=bind,source=preinstall/font-manifests/solidworks-fonts.tsv,target=/mnt/solidworks-fonts.tsv,ro \
    --mount=type=bind,from=solidworks-fonts,target=/mnt/solidworks-fonts,ro \
    bash /mnt/install-fonts.sh \
        /mnt/solidworks-fonts \
        /mnt/solidworks-fonts.tsv \
        solidworks

# 公司设计使用的便利字体同样属于预安装环境，但保持为独立、靠后的字体层。
RUN --mount=type=bind,source=preinstall/install-fonts.sh,target=/mnt/install-fonts.sh,ro \
    --mount=type=bind,source=preinstall/font-manifests/solidworks-custom-fonts.tsv,target=/mnt/solidworks-custom-fonts.tsv,ro \
    --mount=type=bind,from=solidworks-custom-fonts,target=/mnt/solidworks-custom-fonts,ro \
    bash /mnt/install-fonts.sh \
        /mnt/solidworks-custom-fonts \
        /mnt/solidworks-custom-fonts.tsv \
        solidworks-custom

LABEL io.yjbeetle.dockersw.fonts.solidworks="SimSun, Segoe UI" \
      io.yjbeetle.dockersw.fonts.custom="DengXian Light, Microsoft YaHei"

ENV SW_LICENSE_SERVER=

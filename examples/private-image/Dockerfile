# =========================================================================
# 企业内部私有仓库专用 Dockerfile 范例
# 基于公开轻量的 DockerSW 基础运行时，装配企业内部的 SolidWorks 程序与授权
# =========================================================================

# 1. 继承自公开基础运行时
FROM ghcr.io/yjbeetle/dockersw:latest

# 2. 将企业私有存储或 Git LFS 中的 SolidWorks 程序目录装配入镜像
COPY ./SOLIDWORKS /opt/solidworks

# 3. 将 FlexNet 授权服务器与激活文件拷贝至容器
COPY ./SolidWorks_Flexnet_Server /opt/SolidWorks_Flexnet_Server

# 4. 配置开箱即用环境变量：自动拉起容器内授权服务
ENV START_LOCAL_LICENSE=true
ENV SW_INSTALL_DIR=/opt/solidworks
ENV FLEXNET_DIR=/opt/SolidWorks_Flexnet_Server

# 5. （可选）如果使用公司局域网固定浮动许可，可覆盖为远程地址：
# ENV SW_LICENSE_SERVER=25734@192.168.1.100

WORKDIR /workspace

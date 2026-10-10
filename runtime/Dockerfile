# DockerSW: 构建与运行时版本完全一致的 Wine Unix 核心模块。
# win32u、winex11 和 opengl32 直接依赖同次构建的 Wine 私有 ABI，因此必须
# 与 ntdll 成套交付，不能只替换单个 Unix 模块。
# 同版本 x64 combase.dll 负责 SOLIDWORKS 专用的 COM 激活注册等待。
# msxml3.dll 提供 MSXML6 SchemaCache 的命名空间兼容实现（MacSW 0014）。
FROM ubuntu:22.04 AS wine-unix-builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        bison \
        build-essential \
        ca-certificates \
        curl \
        flex \
        gcc-mingw-w64-x86-64 \
        libegl1-mesa-dev \
        libfontconfig1-dev \
        libfreetype6-dev \
        libgl-dev \
        libvulkan-dev \
        libx11-dev \
        libxcomposite-dev \
        libxcursor-dev \
        libxext-dev \
        libxfixes-dev \
        libxi-dev \
        libxinerama-dev \
        libxkbcommon-dev \
        libxkbregistry-dev \
        libxrandr-dev \
        libxrender-dev \
        libxxf86vm-dev \
        patch \
        pkg-config \
        xz-utils && \
    rm -rf /var/lib/apt/lists/*

COPY runtime/managed_com.env /build/managed_com.env
COPY runtime/wine-patches/*.patch /patches/
COPY runtime/tests/native/msxml_schema_namespace_probe.c /build/probes/source.c

RUN . /build/managed_com.env && \
    mkdir -p /build/source /build/output && \
    curl -fsSL \
        "https://dl.winehq.org/wine/source/${WINE_VERSION%%.*}.x/wine-${WINE_VERSION}.tar.xz" \
        -o /build/wine.tar.xz && \
    echo "${WINE_SOURCE_SHA256}  /build/wine.tar.xz" | sha256sum -c - && \
    tar -xf /build/wine.tar.xz -C /build/source --strip-components=1 && \
    for wine_patch in /patches/*.patch; do \
        patch --directory=/build/source --strip=1 --dry-run < "${wine_patch}" && \
        patch --directory=/build/source --strip=1 < "${wine_patch}"; \
    done && \
    mkdir /build/obj && \
    cd /build/obj && \
    ../source/configure \
        --enable-win64 \
        --disable-tests \
        --without-alsa \
        --without-capi \
        --without-cups \
        --without-dbus \
        --without-ffmpeg \
        --without-gettext \
        --without-gettextpo \
        --without-gnutls \
        --without-gphoto \
        --without-gssapi \
        --without-gstreamer \
        --without-inotify \
        --without-krb5 \
        --without-netapi \
        --without-opencl \
        --without-oss \
        --without-pcap \
        --without-pcsclite \
        --without-pulse \
        --without-sane \
        --without-sdl \
        --without-udev \
        --without-usb \
        --without-v4l2 \
        --without-wayland \
        --with-fontconfig \
        --with-freetype \
        --with-opengl \
        --with-vulkan \
        --with-x && \
    make -j"$(nproc)" dlls/win32u/win32u.so dlls/winex11.drv/winex11.so dlls/opengl32/opengl32.so dlls/combase/x86_64-windows/combase.dll dlls/msxml3/x86_64-windows/msxml3.dll && \
    strip --strip-unneeded dlls/ntdll/ntdll.so dlls/win32u/win32u.so dlls/winex11.drv/winex11.so dlls/opengl32/opengl32.so && \
    x86_64-w64-mingw32-strip --strip-debug dlls/combase/x86_64-windows/combase.dll && \
    x86_64-w64-mingw32-strip --strip-debug dlls/msxml3/x86_64-windows/msxml3.dll && \
    install -m 0644 dlls/ntdll/ntdll.so /build/output/ntdll.so && \
    install -m 0644 dlls/win32u/win32u.so /build/output/win32u.so && \
    install -m 0644 dlls/winex11.drv/winex11.so /build/output/winex11.so && \
    install -m 0644 dlls/opengl32/opengl32.so /build/output/opengl32.so && \
    install -m 0644 dlls/combase/x86_64-windows/combase.dll /build/output/combase.dll && \
    install -m 0644 dlls/msxml3/x86_64-windows/msxml3.dll /build/output/msxml3.dll && \
    x86_64-w64-mingw32-gcc -O2 -Wall /build/probes/source.c \
        -o /build/probes/msxml-schema.exe -lole32 -loleaut32

# DockerSW: 无头 SOLIDWORKS Wine 运行时镜像
FROM ubuntu:22.04 AS sw-runtime

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
# jq 是有意内置的运行时工具，方便继承它的 CLI 变体与下游镜像处理结构化输出。
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
# 与 MacSW 已验证环境保持 Wine 11.16 / Wine-Mono 11.3.0 一致。
COPY runtime/managed_com.env /opt/sw-runtime/managed_com.env
COPY --chmod=755 runtime/configure_ui_fonts.sh /usr/local/lib/sw-runtime/configure_ui_fonts.sh
COPY --chmod=755 runtime/prepare_managed_com.sh /usr/local/lib/sw-runtime/prepare_managed_com.sh
COPY --chmod=755 runtime/patch_wine_mono.pl /usr/local/lib/sw-runtime/patch_wine_mono.pl
COPY --from=wine-unix-builder /build/output/ /opt/sw-runtime/wine-unix/

# 3. 安装 Wine、下载 Mono 资产并初始化无头运行环境（合并在单层内执行反向去重，消除 540MB 重复物理占用）
# 仅绑定挂载本层消费的脚本、registry 目录和构建探针，避免把整个
# runtime/ 树纳入缓存键；普通脚本与单测改动不应导致 Wine/Mono/Python 安装
# 无谓重建。原生探针是有意输入，变更后必须重新验证运行时。
RUN --mount=type=bind,from=wine-unix-builder,source=/build/probes,target=/mnt/wine-probes \
    --mount=type=bind,source=runtime/fetch_managed_com.sh,target=/mnt/runtime/fetch_managed_com.sh \
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
    install -m 0644 /opt/sw-runtime/wine-unix/ntdll.so \
        /opt/wine-devel/lib/wine/x86_64-unix/ntdll.so && \
    install -m 0644 /opt/sw-runtime/wine-unix/win32u.so \
        /opt/wine-devel/lib/wine/x86_64-unix/win32u.so && \
    install -m 0644 /opt/sw-runtime/wine-unix/winex11.so \
        /opt/wine-devel/lib/wine/x86_64-unix/winex11.so && \
    install -m 0644 /opt/sw-runtime/wine-unix/opengl32.so \
        /opt/wine-devel/lib/wine/x86_64-unix/opengl32.so && \
    install -m 0644 /opt/sw-runtime/wine-unix/combase.dll \
        /opt/wine-devel/lib/wine/x86_64-windows/combase.dll && \
    install -m 0644 /opt/sw-runtime/wine-unix/msxml3.dll \
        /opt/wine-devel/lib/wine/x86_64-windows/msxml3.dll && \
    rm -rf /opt/sw-runtime/wine-unix && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    bash /mnt/runtime/fetch_managed_com.sh && \
    wget -q "https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-amd64.exe" -O /tmp/python-installer.exe && \
    bash /mnt/runtime/init_wineprefix.sh && \
    { timeout --foreground 120 wine /mnt/wine-probes/msxml-schema.exe > /tmp/msxml-schema-probe.log 2>&1 || \
        { probe_status=$?; cat /tmp/msxml-schema-probe.log >&2; exit "${probe_status}"; }; } && \
    cat /tmp/msxml-schema-probe.log && \
    tr -d '\r' < /tmp/msxml-schema-probe.log > /tmp/msxml-schema-probe.txt && \
    grep -qx 'XML_NAMESPACE_PROBE_PASS' /tmp/msxml-schema-probe.txt && \
    test "$(grep -c '^case=' /tmp/msxml-schema-probe.txt)" -eq 7 && \
    timeout --foreground 60 wineserver -w && \
    rm -rf /tmp/* /root/.cache/*

# 4. 仅加入执行 SOLIDWORKS 官方安装所需的稳定工具。频繁变化的 SWCLI、
# DockerSW 运行脚本与入口点留到正式镜像的交付层。
COPY --chmod=755 runtime/bin/sw-install /usr/local/bin/sw-install
COPY --chmod=755 runtime/entrypoint.sh /usr/local/bin/entrypoint.sh

WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/bin/bash"]

# DockerSW: 当前 SWCLI 与容器适配器组成的内部应用载荷
FROM python:3.11-slim AS swcli-dependencies

# The default runtime uses Linux Python 3.10 and Wine Windows Python 3.11.
# Bundle each platform's wheels in the payload, without rebuilding SOLIDWORKS.
RUN python -m pip install --no-cache-dir --only-binary=:all: \
        --python-version 310 --platform manylinux_2_28_x86_64 --platform manylinux2014_x86_64 \
        --target /deps/linux 'jsonschema>=4.18' && \
    python -m pip install --no-cache-dir --only-binary=:all: \
        --python-version 311 --platform win_amd64 \
        --target /deps/windows 'jsonschema>=4.18'

FROM scratch AS swcli-payload

COPY --link --from=swcli-dependencies /deps/ /opt/swcli-deps/

COPY --link swcli/SWCLI/ /opt/swcli/
COPY --link --chmod=755 \
    swcli/bin/sw-cli \
    swcli/bin/linux-to-wine-path \
    /usr/local/bin/
COPY --link --chmod=755 swcli/entrypoint-cli.sh /usr/local/bin/entrypoint-cli.sh

#!/usr/bin/env sh
set -e

mkdir -p /kaniko/.docker
echo "{\"auths\":{\"https://index.docker.io/v1/\":{\"auth\":\"$(printf "%s:%s" "${DOCKERHUB_USERNAME}" "${DOCKERHUB_PASSWORD}" | base64 | tr -d '\n')\"}}}" > /kaniko/.docker/config.json

SUBMODULE_HASH=$(head -c 7 .git/modules/DockerSW/HEAD 2>/dev/null || true)
echo "检测到子模块 Hash: ${SUBMODULE_HASH}"

DEST_ARGS="--destination ${DOCKERHUB_IMAGE:-yjbeetle/dockersw-complete}:latest"
if [ -n "${SUBMODULE_HASH}" ]; then
  DEST_ARGS="${DEST_ARGS} --destination ${DOCKERHUB_IMAGE:-yjbeetle/dockersw-complete}:sha-${SUBMODULE_HASH}"
fi

echo "开始执行 Kaniko 无特权用户态构建并发布..."
/kaniko/executor --context "${CI_PROJECT_DIR}" --dockerfile "${CI_PROJECT_DIR}/Dockerfile" ${DEST_ARGS}

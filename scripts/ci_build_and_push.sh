#!/usr/bin/env sh
set -e

REGISTRY_ROOT="${CI_REGISTRY_IMAGE:?Set CI_REGISTRY_IMAGE to the GitLab Registry repository}"
DOCKER_IMAGE_NAME="${REGISTRY_ROOT}/sw-preinstalled"
DOCKER_IMAGE_TAG="${CI_COMMIT_TAG:-latest}"
SUBMODULE_HASH=$(git -C DockerSW rev-parse --short HEAD 2>/dev/null || echo "")

if [ -z "${CI_REGISTRY:-}" ] || [ -z "${CI_REGISTRY_USER:-}" ] || [ -z "${CI_REGISTRY_PASSWORD:-}" ]; then
  echo "=================================================================================="
  echo " [ERROR] 未检测到 GitLab Container Registry 凭据环境变量！"
  echo " 请在 GitLab 项目页面配置以下凭据变量并重新运行流水线："
  echo "   路径: Settings -> CI/CD -> Variables -> Add variable"
  echo "   - CI_REGISTRY"
  echo "   - CI_REGISTRY_USER"
  echo "   - CI_REGISTRY_PASSWORD"
  echo "   - CI_REGISTRY_IMAGE"
  echo "=================================================================================="
  exit 1
fi

echo "[1/4] 正在登录 GitLab Container Registry (${CI_REGISTRY})..."
echo "${CI_REGISTRY_PASSWORD}" | docker login "${CI_REGISTRY}" -u "${CI_REGISTRY_USER}" --password-stdin

BASE_IMAGE="${BASE_IMAGE:-${REGISTRY_ROOT}/sw-runtime:sha-${SUBMODULE_HASH}}"
echo "使用基础镜像 BASE_IMAGE=${BASE_IMAGE}"
BUILD_ARGS="--build-arg BASE_IMAGE=${BASE_IMAGE}"

echo "[2/4] 正在构建一体化 SolidWorks 容器镜像: ${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG} (Submodule Hash: ${SUBMODULE_HASH:-unknown})..."
docker build ${BUILD_ARGS} -t "${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG}" .

if [ -n "${SUBMODULE_HASH}" ]; then
  echo "为镜像打上 Submodule Commit 标签: ${DOCKER_IMAGE_NAME}:sha-${SUBMODULE_HASH}"
  docker tag "${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG}" "${DOCKER_IMAGE_NAME}:sha-${SUBMODULE_HASH}"
fi

echo "[3/4] 正在推送至 GitLab Container Registry: ${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG}..."
docker push "${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG}"
if [ -n "${SUBMODULE_HASH}" ]; then
  docker push "${DOCKER_IMAGE_NAME}:sha-${SUBMODULE_HASH}"
fi

echo "[4/4] Docker 镜像成功构建并发布至 GitLab Container Registry: ${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG}"
if [ -n "${SUBMODULE_HASH}" ]; then
  echo "       同步标签: ${DOCKER_IMAGE_NAME}:sha-${SUBMODULE_HASH}"
fi

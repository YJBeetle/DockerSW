#!/usr/bin/env sh
set -e

DOCKER_IMAGE_NAME="${DOCKERHUB_IMAGE:-yjbeetle/dockersw-complete}"
DOCKER_IMAGE_TAG="${CI_COMMIT_TAG:-latest}"
SUBMODULE_HASH=$(git -C DockerSW rev-parse --short HEAD 2>/dev/null || echo "")

if [ -z "${DOCKERHUB_USERNAME:-}" ] || [ -z "${DOCKERHUB_PASSWORD:-}" ]; then
  echo "=================================================================================="
  echo " [ERROR] 未检测到 Docker Hub 凭据环境变量！"
  echo " 请在 GitLab 项目页面配置以下凭据变量并重新运行流水线："
  echo "   路径: Settings -> CI/CD -> Variables -> Add variable"
  echo "   - DOCKERHUB_USERNAME: 你的 Docker Hub 用户名"
  echo "   - DOCKERHUB_PASSWORD: 你的 Docker Hub Access Token 或密码 (建议勾选 Masked)"
  echo "   - DOCKERHUB_IMAGE (可选): 目标镜像名，默认 yjbeetle/dockersw-complete"
  echo "=================================================================================="
  exit 1
fi

echo "[1/4] 正在登录 Docker Hub (${DOCKERHUB_USERNAME})..."
echo "${DOCKERHUB_PASSWORD}" | docker login -u "${DOCKERHUB_USERNAME}" --password-stdin

BUILD_ARGS=""
if [ -n "${BASE_IMAGE:-}" ]; then
  echo "指定基础镜像 BASE_IMAGE=${BASE_IMAGE}"
  BUILD_ARGS="--build-arg BASE_IMAGE=${BASE_IMAGE}"
fi

echo "[2/4] 正在构建一体化 SolidWorks 容器镜像: ${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG} (Submodule Hash: ${SUBMODULE_HASH:-unknown})..."
docker build ${BUILD_ARGS} -t "${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG}" .

if [ -n "${SUBMODULE_HASH}" ]; then
  echo "为镜像打上 Submodule Commit 标签: ${DOCKER_IMAGE_NAME}:sha-${SUBMODULE_HASH}"
  docker tag "${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG}" "${DOCKER_IMAGE_NAME}:sha-${SUBMODULE_HASH}"
fi

echo "[3/4] 正在推送至 Docker Hub: ${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG}..."
docker push "${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG}"
if [ -n "${SUBMODULE_HASH}" ]; then
  docker push "${DOCKER_IMAGE_NAME}:sha-${SUBMODULE_HASH}"
fi

echo "[4/4] 恭喜！Docker 镜像成功构建并发布至 Docker Hub: ${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG}"
if [ -n "${SUBMODULE_HASH}" ]; then
  echo "       同步标签: ${DOCKER_IMAGE_NAME}:sha-${SUBMODULE_HASH}"
fi

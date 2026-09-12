#!/usr/bin/env sh
set -eu

: "${CI_PROJECT_DIR:?CI_PROJECT_DIR is required}"
: "${CI_REGISTRY_IMAGE:?CI_REGISTRY_IMAGE is required}"

SUBMODULE_HASH="$(sh "${CI_PROJECT_DIR}/scripts/resolve_submodule_hash.sh")"
RUNTIME_IMAGE="${CI_REGISTRY_IMAGE}/runtime:sha-${SUBMODULE_HASH}"

echo "Building DockerSW runtime from submodule ${SUBMODULE_HASH}..."
/kaniko/executor \
  --context "${CI_PROJECT_DIR}/DockerSW" \
  --dockerfile "${CI_PROJECT_DIR}/DockerSW/docker/Dockerfile" \
  --destination "${RUNTIME_IMAGE}" \
  --push-retry 5 \
  --image-download-retry 3 \
  --image-fs-extract-retry 3

echo "DockerSW runtime pushed to GitLab Registry: ${RUNTIME_IMAGE}"

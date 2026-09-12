#!/usr/bin/env sh
set -eu

: "${CI_PROJECT_DIR:?CI_PROJECT_DIR is required}"
: "${CI_REGISTRY_IMAGE:?CI_REGISTRY_IMAGE is required}"

SUBMODULE_HASH="$(sh "${CI_PROJECT_DIR}/scripts/resolve_submodule_hash.sh")"
RUNTIME_TAG="$(printf '%.7s' "${SUBMODULE_HASH}")"
RUNTIME_IMAGE="${DOCKERSW_RUNTIME_IMAGE:-${CI_REGISTRY_IMAGE}/runtime:sha-${RUNTIME_TAG}}"

set -- \
  --destination "${CI_REGISTRY_IMAGE}:latest" \
  --destination "${CI_REGISTRY_IMAGE}:sha-${CI_COMMIT_SHORT_SHA}"

if [ -n "${CI_COMMIT_TAG:-}" ]; then
  set -- "$@" --destination "${CI_REGISTRY_IMAGE}:${CI_COMMIT_TAG}"
fi

echo "Building private DockerSWComplete from mirrored runtime ${RUNTIME_IMAGE}..."
/kaniko/executor \
  --context "${CI_PROJECT_DIR}" \
  --dockerfile "${CI_PROJECT_DIR}/Dockerfile" \
  --build-arg "BASE_IMAGE=${RUNTIME_IMAGE}" \
  --build-arg "SW_INSTALL_TIMEOUT=${SW_INSTALL_TIMEOUT:-10800}" \
  --push-retry 5 \
  --image-download-retry 3 \
  --image-fs-extract-retry 3 \
  "$@"

echo "DockerSWComplete pushed to GitLab Registry: ${CI_REGISTRY_IMAGE}"

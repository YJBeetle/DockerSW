#!/usr/bin/env sh
set -eu

: "${CI_PROJECT_DIR:?CI_PROJECT_DIR is required}"
: "${CI_REGISTRY:?CI_REGISTRY is required}"
: "${CI_REGISTRY_USER:?CI_REGISTRY_USER is required}"
: "${CI_REGISTRY_PASSWORD:?CI_REGISTRY_PASSWORD is required}"
: "${CI_REGISTRY_IMAGE:?CI_REGISTRY_IMAGE is required}"

SUBMODULE_HASH="$(sh "${CI_PROJECT_DIR}/scripts/resolve_submodule_hash.sh")"
RUNTIME_TAG="$(printf '%.7s' "${SUBMODULE_HASH}")"
SOURCE_IMAGE="ghcr.io/yjbeetle/dockersw:sha-${RUNTIME_TAG}"
DESTINATION_IMAGE="${CI_REGISTRY_IMAGE}/runtime:sha-${RUNTIME_TAG}"

printf '%s' "${CI_REGISTRY_PASSWORD}" | \
  crane auth login "${CI_REGISTRY}" \
    --username "${CI_REGISTRY_USER}" \
    --password-stdin >/dev/null

if crane manifest "${DESTINATION_IMAGE}" >/dev/null 2>&1; then
  echo "DockerSW runtime already exists in GitLab Registry: ${DESTINATION_IMAGE}"
  exit 0
fi

echo "Mirroring DockerSW runtime from GHCR to GitLab Registry..."
attempt=1
while ! crane copy --platform linux/amd64 "${SOURCE_IMAGE}" "${DESTINATION_IMAGE}"; do
  if [ "${attempt}" -ge 5 ]; then
    echo "Unable to mirror DockerSW runtime after ${attempt} attempts" >&2
    exit 1
  fi
  delay=$((attempt * 5))
  echo "Runtime mirror attempt ${attempt} failed; retrying in ${delay}s..." >&2
  sleep "${delay}"
  attempt=$((attempt + 1))
done

crane manifest "${DESTINATION_IMAGE}" >/dev/null
echo "DockerSW runtime mirrored to GitLab Registry: ${DESTINATION_IMAGE}"

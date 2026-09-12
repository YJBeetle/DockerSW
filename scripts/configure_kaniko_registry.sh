#!/usr/bin/env sh
set -eu

: "${CI_REGISTRY:?CI_REGISTRY is required}"
: "${CI_REGISTRY_USER:?CI_REGISTRY_USER is required}"
: "${CI_REGISTRY_PASSWORD:?CI_REGISTRY_PASSWORD is required}"

mkdir -p /kaniko/.docker
REGISTRY_AUTH="$(printf '%s:%s' "${CI_REGISTRY_USER}" "${CI_REGISTRY_PASSWORD}" | base64 | tr -d '\n')"
printf '{"auths":{"%s":{"auth":"%s"}}}\n' \
  "${CI_REGISTRY}" "${REGISTRY_AUTH}" > /kaniko/.docker/config.json

echo "GitLab Container Registry authentication configured."

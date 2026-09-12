#!/usr/bin/env sh
set -eu

: "${SW_MEDIA_SHA256:?Set SW_MEDIA_SHA256 to the approved media digest}"

MEDIA_DIR="${CI_PROJECT_DIR:-$(pwd)}/.ci-media"
MEDIA_TARGET="${MEDIA_DIR}/solidworks-media"
mkdir -p "${MEDIA_DIR}"
rm -f "${MEDIA_TARGET}"

if [ -n "${SW_MEDIA_LOCAL_PATH:-}" ]; then
  [ -f "${SW_MEDIA_LOCAL_PATH}" ] || {
    echo "SW_MEDIA_LOCAL_PATH does not point to a mounted file" >&2
    exit 1
  }
  echo "Copying SOLIDWORKS media from the private runner mount..."
  cp "${SW_MEDIA_LOCAL_PATH}" "${MEDIA_TARGET}"
else
  : "${SW_MEDIA_URL:?Set SW_MEDIA_URL or SW_MEDIA_LOCAL_PATH}"
  echo "Downloading SOLIDWORKS media from the configured private source..."

  # 这些参数同时兼容 GNU wget 与 Kaniko debug 镜像中的 BusyBox wget。
  set -- -q -t 3 -T 60 -O "${MEDIA_TARGET}"
  if [ -n "${SW_MEDIA_BEARER_TOKEN:-}" ]; then
    set -- "$@" --header "Authorization: Bearer ${SW_MEDIA_BEARER_TOKEN}"
  elif [ -n "${SW_MEDIA_USERNAME:-}" ] || [ -n "${SW_MEDIA_PASSWORD:-}" ]; then
    : "${SW_MEDIA_USERNAME:?Both SW_MEDIA_USERNAME and SW_MEDIA_PASSWORD are required}"
    : "${SW_MEDIA_PASSWORD:?Both SW_MEDIA_USERNAME and SW_MEDIA_PASSWORD are required}"
    BASIC_AUTH="$(printf '%s:%s' "${SW_MEDIA_USERNAME}" "${SW_MEDIA_PASSWORD}" | base64 | tr -d '\n')"
    set -- "$@" --header "Authorization: Basic ${BASIC_AUTH}"
  fi

  if command -v wget >/dev/null 2>&1; then
    wget "$@" "${SW_MEDIA_URL}"
  else
    /busybox/wget "$@" "${SW_MEDIA_URL}"
  fi
fi

if command -v sha256sum >/dev/null 2>&1; then
  ACTUAL_SHA256="$(sha256sum "${MEDIA_TARGET}" | awk '{print $1}')"
else
  ACTUAL_SHA256="$(shasum -a 256 "${MEDIA_TARGET}" | awk '{print $1}')"
fi
if [ "${ACTUAL_SHA256}" != "${SW_MEDIA_SHA256}" ]; then
  rm -f "${MEDIA_TARGET}"
  echo "SOLIDWORKS media checksum mismatch" >&2
  exit 1
fi

echo "Private SOLIDWORKS media checksum verified."

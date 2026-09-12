#!/usr/bin/env sh
set -eu

PROJECT_DIR="${CI_PROJECT_DIR:-$(pwd)}"
GIT_POINTER="${PROJECT_DIR}/DockerSW/.git"
[ -f "${GIT_POINTER}" ] || {
  echo "DockerSW submodule git pointer is missing" >&2
  exit 1
}

GIT_DIR_RELATIVE="$(sed -n 's/^gitdir: //p' "${GIT_POINTER}")"
[ -n "${GIT_DIR_RELATIVE}" ] || {
  echo "DockerSW submodule git pointer is invalid" >&2
  exit 1
}
GIT_DIR="${PROJECT_DIR}/DockerSW/${GIT_DIR_RELATIVE}"
HEAD_VALUE="$(sed -n '1p' "${GIT_DIR}/HEAD")"

case "${HEAD_VALUE}" in
  'ref: '*)
    REF_NAME="${HEAD_VALUE#ref: }"
    if [ -f "${GIT_DIR}/${REF_NAME}" ]; then
      FULL_HASH="$(sed -n '1p' "${GIT_DIR}/${REF_NAME}")"
    elif [ -f "${GIT_DIR}/packed-refs" ]; then
      FULL_HASH="$(awk -v ref="${REF_NAME}" '$2 == ref { print $1; exit }' "${GIT_DIR}/packed-refs")"
    else
      FULL_HASH=""
    fi
    ;;
  *)
    FULL_HASH="${HEAD_VALUE}"
    ;;
esac

case "${FULL_HASH}" in
  *[!0-9a-f]*|'')
    echo "Unable to resolve the DockerSW submodule commit" >&2
    exit 1
    ;;
esac

printf '%.12s\n' "${FULL_HASH}"

#!/usr/bin/env bash
set -euo pipefail

FONTS_KEY='HKLM\Software\Microsoft\Windows NT\CurrentVersion\Fonts'
SUBSTITUTES_KEY='HKLM\Software\Microsoft\Windows NT\CurrentVersion\FontSubstitutes'
SYSTEM_LINK_KEY='HKLM\Software\Microsoft\Windows NT\CurrentVersion\FontLink\SystemLink'
NOTO_LINK='NotoSansCJK-Regular.ttc,Noto Sans CJK SC'

font_registry="$(wine reg query "${FONTS_KEY}" /s 2>/dev/null)" \
    || { echo '[DockerSW Build][ERROR] 无法读取 Wine 字体注册表' >&2; exit 1; }
printf '%s\n' "${font_registry}" | grep -Fq 'NotoSansCJK-Regular.ttc' \
    || { echo '[DockerSW Build][ERROR] Wine 未登记 Noto Sans CJK 字体' >&2; exit 1; }

tahoma_query="$(wine reg query "${SYSTEM_LINK_KEY}" /v Tahoma 2>/dev/null)" \
    || { echo '[DockerSW Build][ERROR] 无法读取 Wine 的 Tahoma 字体链接' >&2; exit 1; }
tahoma_links="$(
    printf '%s\n' "${tahoma_query}" \
        | sed -nE 's/.*REG_MULTI_SZ[[:space:]]+(.*)$/\1/p' \
        | head -n 1
)"
[ -n "${tahoma_links}" ] \
    || { echo '[DockerSW Build][ERROR] Wine 的 Tahoma 字体链接为空' >&2; exit 1; }

case "${tahoma_links}" in
    "${NOTO_LINK}"|"${NOTO_LINK}\\0"*) ;;
    *) tahoma_links="${NOTO_LINK}\\0${tahoma_links}" ;;
esac

# MS Shell Dlg / MS Shell Dlg 2 是 Windows 的逻辑界面字体。只重定向这两个
# UI 别名，并通过 Tahoma 的缺字链接补充简体中文；不要替换工程图可能显式
# 使用的 Arial、Times New Roman、SimSun 或 Microsoft YaHei 等字体。
wine reg add "${SUBSTITUTES_KEY}" /v 'MS Shell Dlg' /t REG_SZ /d Tahoma /f >/dev/null
wine reg add "${SUBSTITUTES_KEY}" /v 'MS Shell Dlg 2' /t REG_SZ /d Tahoma /f >/dev/null
wine reg add "${SYSTEM_LINK_KEY}" /v Tahoma /t REG_MULTI_SZ /d "${tahoma_links}" /f >/dev/null

verified_link="$(wine reg query "${SYSTEM_LINK_KEY}" /v Tahoma 2>/dev/null)"
printf '%s\n' "${verified_link}" | grep -Fq "${NOTO_LINK}" \
    || { echo '[DockerSW Build][ERROR] Noto 界面字体链接写入后校验失败' >&2; exit 1; }

echo '[DockerSW Build] 已配置 Noto Sans CJK SC 作为 Windows 界面的中文缺字回退。'

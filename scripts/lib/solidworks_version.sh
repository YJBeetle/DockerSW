#!/usr/bin/env bash

# Convert the core SOLIDWORKS MSI ProductVersion into:
#   <product year>\t<service-pack major>\t<service-pack minor>
#
# The first field is the annual major code (32 = 2024, 33 = 2025). The
# second field is an internal update code: 100 = SP0.0, 150 = SP5.0, and
# 132 = SP3.2. The third field is a build number and is intentionally ignored.
solidworks_release_from_product_version() {
    local product_version="${1:-}"
    local major_code update_code product_year service_pack_code

    [[ "${product_version}" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)(\.|$) ]] || return 1
    major_code="$((10#${BASH_REMATCH[1]}))"
    update_code="$((10#${BASH_REMATCH[2]}))"
    product_year="$((major_code + 1992))"

    [ "${product_year}" -ge 2000 ] && [ "${product_year}" -le 2100 ] || return 1
    [ "${update_code}" -ge 100 ] && [ "${update_code}" -le 199 ] || return 1

    service_pack_code="$((update_code - 100))"
    printf '%s\t%s\t%s\n' \
        "${product_year}" \
        "$((service_pack_code / 10))" \
        "$((service_pack_code % 10))"
}

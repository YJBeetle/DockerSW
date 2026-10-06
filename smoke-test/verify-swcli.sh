#!/usr/bin/env bash
set -Eeuo pipefail

workspace="${1:?usage: verify-swcli.sh WINE_DRIVE_C}"
part_path="${workspace}/users/Public/Documents/SOLIDWORKS/SOLIDWORKS 2025/samples/learn/Paper Airplane.SLDPRT"
assembly_path="${workspace}/Program Files/SOLIDWORKS/sldBenchmarking/Macro/Mold/bezel moldbase.sldasm"

# The client validates this response against capabilities.schema.json.
sw-cli capabilities --json

# Unsaved documents have no path: their handles must still remain distinct.
created_a="$(sw-cli document create --type part --json)"
created_b="$(sw-cli document create --json)"
printf '%s\n' "${created_a}" "${created_b}"
created_a_id="$(printf '%s' "${created_a}" | jq -er \
    'select(.created == true and .document.path == "" and .document.type == 1) | .document.document_id')"
printf '%s' "${created_b}" | jq -e --arg first "${created_a_id}" \
    '.created == true and .document.path == "" and .document.type == 1
     and .document.document_id != $first' >/dev/null || {
    echo "New unsaved parts did not receive distinct document handles" >&2
    exit 1
}

# Create geometry in background part A; every operation must restore part B.
# These sketches are discarded and do not change the six published artifacts.
for plane in front top right; do
    rectangle_json="$(sw-cli sketch rectangle --plane "${plane}" \
        --width-mm 100 --height-mm 50 --center-x-mm 10 --center-y-mm 20 \
        --document "${created_a_id}" --json)"
    printf '%s\n' "${rectangle_json}"
    printf '%s' "${rectangle_json}" | jq -e --arg plane "${plane}" \
        '.plane == $plane and .coordinate_system == "sketch-local"
         and .editing == false and .geometry_verification.passed == true
         and .geometry_verification.profile_segment_count == 4
         and (.sketch.sketch_id | test("^s-[a-z0-9]{6}$"))
         and .document.active == false and .document.current == false' >/dev/null || {
        echo "Rectangle on ${plane} failed geometry or foreground restoration checks" >&2
        exit 1
    }
done
created_b_id="$(printf '%s' "${created_b}" | jq -er '.document.document_id')"
sw-cli document inspect --json | jq -e --arg id "${created_b_id}" \
    '.document.document_id == $id
     and .document.active == true and .document.current == true' >/dev/null || {
    echo "The foreground part was not restored after rectangle creation" >&2
    exit 1
}
sw-cli document close --document "${created_a_id}" --discard --json
sw-cli document close --discard --json

part_json="$(sw-cli document open "${part_path}" --json)"
printf '%s\n' "${part_json}"
part_id="$(printf '%s' "${part_json}" | jq -er '.document.document_id')"

# GetUpdateStamp must work on the real Wine/SOLIDWORKS host so optimistic
# concurrency checks cannot silently degrade to null.
inspect_json="$(sw-cli document inspect --document "${part_id}" --json)"
printf '%s\n' "${inspect_json}"
printf '%s' "${inspect_json}" | jq -e '.document.update_stamp != null' >/dev/null || {
    echo "GetUpdateStamp is unavailable on this Wine/SOLIDWORKS host" >&2
    exit 1
}

# A competing session must be rejected while the lease owner may export.
lease_json="$(sw-cli --session smoke-owner document lease acquire \
    --document "${part_id}" --ttl-seconds 60 --json)"
printf '%s\n' "${lease_json}"
lease_id="$(printf '%s' "${lease_json}" | jq -er '.lease.lease_id')"

if conflict_json="$(sw-cli --session smoke-contender document export \
    /tmp/swcli-smoke-lease-denied.STEP --document "${part_id}" --json 2>&1)"; then
    echo "A competing session exported a leased document" >&2
    exit 1
fi
printf '%s\n' "${conflict_json}"
printf '%s' "${conflict_json}" | jq -e \
    '.error.type == "DocumentLeaseConflict"' >/dev/null || {
    echo "A competing session failed for an unexpected reason" >&2
    exit 1
}

# Additional verification artifacts stay outside the six published outputs.
sw-cli --session smoke-owner document export \
    /tmp/swcli-smoke-leased.STEP \
    --document "${part_id}" \
    --lease "${lease_id}" \
    --json
test -s /tmp/swcli-smoke-leased.STEP
sw-cli --session smoke-owner document lease release "${lease_id}" --json

# Keep part A open, then open assembly B. Exporting A by ID must temporarily
# activate it and restore B as both the active and current document.
assembly_json="$(sw-cli document open "${assembly_path}" --json)"
printf '%s\n' "${assembly_json}"
assembly_id="$(printf '%s' "${assembly_json}" | jq -er '.document.document_id')"

list_json="$(sw-cli document list --json)"
printf '%s\n' "${list_json}"
printf '%s' "${list_json}" | jq -e --arg id "${part_id}" \
    '[.documents[] | select(.document_id == $id)] | length == 1' >/dev/null || {
    echo "The part is missing from the daemon document registry" >&2
    exit 1
}
printf '%s' "${list_json}" | jq -e --arg id "${assembly_id}" \
    '[.documents[] | select(.document_id == $id)] | length == 1' >/dev/null || {
    echo "The assembly is missing from the daemon document registry" >&2
    exit 1
}

sw-cli document export /tmp/swcli-smoke-multi-document.STEP \
    --document "${part_id}" --json
test -s /tmp/swcli-smoke-multi-document.STEP

list_json="$(sw-cli document list --json)"
printf '%s\n' "${list_json}"
printf '%s' "${list_json}" | jq -e --arg id "${part_id}" \
    '[.documents[] | select(.document_id == $id)]
     | length == 1 and .[0].active == false and .[0].current == false' >/dev/null || {
    echo "The background part remained active or current after export" >&2
    exit 1
}
printf '%s' "${list_json}" | jq -e --arg id "${assembly_id}" \
    '[.documents[] | select(.document_id == $id)]
     | length == 1 and .[0].active == true and .[0].current == true' >/dev/null || {
    echo "The foreground assembly was not restored after background export" >&2
    exit 1
}

sw-cli document close --discard --json
sw-cli document close --discard --document "${part_id}" --json

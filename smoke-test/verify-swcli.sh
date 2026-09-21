#!/usr/bin/env bash
set -Eeuo pipefail

workspace="${1:?usage: verify-swcli.sh WINE_DRIVE_C}"
part_path="${workspace}/users/Public/Documents/SOLIDWORKS/SOLIDWORKS 2025/samples/learn/Paper Airplane.SLDPRT"
assembly_path="${workspace}/Program Files/SOLIDWORKS/sldBenchmarking/Macro/Mold/bezel moldbase.sldasm"

# The client validates this response against capabilities.schema.json.
sw-cli capabilities --json

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

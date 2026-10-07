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
# The additional native model stays outside the six published artifacts.
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
    sketch_id="$(printf '%s' "${rectangle_json}" | jq -er '.sketch.sketch_id')"
    extrusion_json="$(sw-cli feature extrude "${sketch_id}" --depth-mm 20 \
        --document "${created_a_id}" --json)"
    printf '%s\n' "${extrusion_json}"
    printf '%s' "${extrusion_json}" | jq -e \
        '.geometry_verification.passed == true
         and .geometry_verification.actual_depth_mm == 20
         and .geometry_verification.actual_reverse == false
         and .geometry_verification.actual_merge == true
         and .bodies.count > 0
         and .document.active == false and .document.current == false' >/dev/null || {
        echo "Extrusion on ${plane} failed native definition or foreground checks" >&2
        exit 1
    }
    if [[ "${plane}" == front ]]; then
        sw-cli document measure --document "${created_a_id}" --json | jq -e \
            '.metrics.solid_body_count == 1
             and ((.metrics.volume_mm3 - 100000) | fabs) < 0.00001
             and ((.metrics.surface_area_mm2 - 16000) | fabs) < 0.00001
             and .document.active == false and .document.current == false' >/dev/null || {
            echo "First extrusion failed native volume or surface-area checks" >&2
            exit 1
        }
        hole_json="$(sw-cli sketch circle --plane front --radius-mm 4 \
            --center-x-mm 10 --center-y-mm 20 --document "${created_a_id}" --json)"
        hole_id="$(printf '%s' "${hole_json}" | jq -er '.sketch.sketch_id')"
        hole_stamp="$(printf '%s' "${hole_json}" | jq -er '.document.update_stamp')"
        sw-cli --session smoke-observer sketch inspect "${hole_id}" \
            --document "${created_a_id}" --if-update-stamp "${hole_stamp}" --json | jq -e --argjson stamp "${hole_stamp}" \
            '.geometry_complete == true and .sketch.absorbed == false and .editing == false
             and .profile_segment_count == 1 and .segments[0].geometry.complete_circle == true
             and ((.segments[0].geometry.radius_mm - 4) | fabs) < 0.000001
             and .document.update_stamp == $stamp
             and .document.active == false and .document.current == false' >/dev/null || {
            echo "Read-only circle observation failed geometry or foreground checks" >&2
            exit 1
        }
        cut_json="$(sw-cli feature cut-extrude "${hole_id}" --depth-mm 20 \
            --document "${created_a_id}" --json)"
        printf '%s\n' "${hole_json}" "${cut_json}"
        printf '%s' "${cut_json}" | jq -e --argjson pi 3.141592653589793 \
            '.geometry_verification.passed == true
             and .geometry_verification.actual_reverse == false
             and ((.geometry_verification.volume_removed_mm3 - (320 * $pi)) | fabs) < 0.00001
             and ((.measurement_after.surface_area_mm2 - (16000 + 128 * $pi)) | fabs) < 0.00001
             and .document.active == false and .document.current == false' >/dev/null || {
            echo "Blind cut failed native direction, hole geometry or foreground checks" >&2
            exit 1
        }
        cut_name="$(printf '%s' "${cut_json}" | jq -er '.feature.name')"
        cut_stamp="$(printf '%s' "${cut_json}" | jq -er '.document.update_stamp')"
        sw-cli --session smoke-observer sketch inspect "${hole_id}" \
            --document "${created_a_id}" --if-update-stamp "${cut_stamp}" --json | \
            jq -e --arg owner "${cut_name}" --argjson stamp "${cut_stamp}" \
            '.sketch.absorbed == true and .sketch.owner.name == $owner
             and .geometry_complete == true and .editing == false
             and .document.update_stamp == $stamp
             and .document.active == false and .document.current == false' >/dev/null || {
            echo "Absorbed sketch observation lost native owner identity or changed foreground" >&2
            exit 1
        }
        if denied_json="$(sw-cli feature cut-extrude "${hole_id}" --depth-mm 20 \
            --document "${created_a_id}" --json 2>&1)"; then
            echo "An absorbed cut profile was reused to create another feature" >&2
            exit 1
        fi
        printf '%s' "${denied_json}" | jq -e '.error.type == "SketchUnavailable"' >/dev/null || {
            echo "Absorbed cut profile failed for an unexpected reason: ${denied_json}" >&2
            exit 1
        }
    fi
done
for plane in front top right; do
    circle_json="$(sw-cli sketch circle --plane "${plane}" --radius-mm 8 \
        --center-x-mm 120 --center-y-mm 20 --document "${created_a_id}" --json)"
    printf '%s\n' "${circle_json}"
    printf '%s' "${circle_json}" | jq -e \
        '.geometry_verification.passed == true
         and .geometry_verification.complete_circle == true
         and .geometry_verification.profile_segment_count == 1
         and .editing == false
         and .document.active == false and .document.current == false' >/dev/null || {
        echo "Circle on ${plane} failed native geometry or foreground checks" >&2
        exit 1
    }
    sketch_id="$(printf '%s' "${circle_json}" | jq -er '.sketch.sketch_id')"
    extrusion_json="$(sw-cli feature extrude "${sketch_id}" --depth-mm 20 --no-merge \
        --document "${created_a_id}" --json)"
    printf '%s\n' "${extrusion_json}"
    printf '%s' "${extrusion_json}" | jq -e \
        '.geometry_verification.passed == true
         and .geometry_verification.actual_merge == false
         and .document.active == false and .document.current == false' >/dev/null || {
        echo "Circle extrusion on ${plane} failed native definition checks" >&2
        exit 1
    }
done
created_b_id="$(printf '%s' "${created_b}" | jq -er '.document.document_id')"
sw-cli document inspect --json | jq -e --arg id "${created_b_id}" \
    '.document.document_id == $id
     and .document.active == true and .document.current == true' >/dev/null || {
    echo "The foreground part was not restored after modeling" >&2
    exit 1
}
native_path=/tmp/swcli-smoke-generic.SLDPRT
measurement_json="$(sw-cli document measure --document "${created_a_id}" --json)"
printf '%s\n' "${measurement_json}"
volume="$(printf '%s' "${measurement_json}" | jq -er '.metrics.volume_mm3')"
area="$(printf '%s' "${measurement_json}" | jq -er '.metrics.surface_area_mm2')"
saved_json="$(sw-cli document save-as "${native_path}" \
    --document "${created_a_id}" --json)"
printf '%s\n' "${saved_json}"
printf '%s' "${saved_json}" | jq -e --arg id "${created_a_id}" \
    '.document.document_id == $id and .document.modified == false
     and .document.active == false and .document.current == false
     and .file_verification.minimum_size_valid == true' >/dev/null || {
    echo "Native save-as lost document identity or left an invalid state" >&2
    exit 1
}
test -s "${native_path}"
body_count="$(printf '%s' "${extrusion_json}" | jq -er '.bodies.count')"
sw-cli document close --document "${created_a_id}" --discard --json
sw-cli --session smoke-reopen document open "${native_path}" --read-only --json
sw-cli --session smoke-reopen document inspect --detail structure --json | \
    jq -e --argjson count "${body_count}" '.structure.bodies.count == $count' >/dev/null || {
    echo "Native save/reopen changed solid body count" >&2
    exit 1
}
sw-cli --session smoke-reopen document diagnose --json | \
    jq -e '.diagnostics.healthy == true and .needs_rebuild == 0' >/dev/null || {
    echo "Reopened native model failed rebuild or feature diagnosis" >&2
    exit 1
}
sw-cli --session smoke-reopen document measure --json | \
    jq -e --argjson volume "${volume}" --argjson area "${area}" \
    '((.metrics.volume_mm3 - $volume) | fabs) <= ($volume * 0.000000001 + 0.00001)
     and ((.metrics.surface_area_mm2 - $area) | fabs) <= ($area * 0.000000001 + 0.00001)' >/dev/null || {
    echo "Native save/reopen changed measured volume or surface area" >&2
    exit 1
}
sw-cli --session smoke-reopen document close --discard --json

# --reverse means opposite the sketch normal for both bosses and cuts.
sw-cli --session smoke-reverse document create --json
rectangle_json="$(sw-cli --session smoke-reverse sketch rectangle --plane front \
    --width-mm 40 --height-mm 30 --json)"
sketch_id="$(printf '%s' "${rectangle_json}" | jq -er '.sketch.sketch_id')"
sw-cli --session smoke-reverse feature extrude "${sketch_id}" --depth-mm 10 --reverse --json
circle_json="$(sw-cli --session smoke-reverse sketch circle --plane front --radius-mm 3 --json)"
sketch_id="$(printf '%s' "${circle_json}" | jq -er '.sketch.sketch_id')"
sw-cli --session smoke-reverse feature cut-extrude "${sketch_id}" --depth-mm 10 --reverse --json | \
    jq -e --argjson pi 3.141592653589793 \
        '.geometry_verification.passed == true and .geometry_verification.actual_reverse == true
         and ((.geometry_verification.volume_removed_mm3 - (90 * $pi)) | fabs) < 0.00001' >/dev/null || {
    echo "Reverse cut did not remove the expected material against the sketch normal" >&2
    exit 1
}
sw-cli --session smoke-reverse document close --discard --json

# Native rejection is also evidence: a nonintersecting profile cannot be a cut.
sw-cli --session smoke-cut-failure document create --json
rectangle_json="$(sw-cli --session smoke-cut-failure sketch rectangle --plane front \
    --width-mm 40 --height-mm 30 --json)"
sketch_id="$(printf '%s' "${rectangle_json}" | jq -er '.sketch.sketch_id')"
sw-cli --session smoke-cut-failure feature extrude "${sketch_id}" --depth-mm 10 --json
circle_json="$(sw-cli --session smoke-cut-failure sketch circle --plane front \
    --radius-mm 2 --center-x-mm 1000 --json)"
sketch_id="$(printf '%s' "${circle_json}" | jq -er '.sketch.sketch_id')"
if denied_json="$(sw-cli --session smoke-cut-failure feature cut-extrude \
    "${sketch_id}" --depth-mm 10 --json 2>&1)"; then
    echo "A nonintersecting profile was reported as a successful cut" >&2
    exit 1
fi
printf '%s' "${denied_json}" | jq -e '.error.type == "CutExtrusionFailed"' >/dev/null || {
    echo "Nonintersecting cut failed for an unexpected reason: ${denied_json}" >&2
    exit 1
}
sw-cli --session smoke-cut-failure document measure --json | jq -e \
    '.metrics.solid_body_count == 1 and ((.metrics.volume_mm3 - 12000) | fabs) < 0.00001' >/dev/null || {
    echo "Nonintersecting cut failure changed the measured solid" >&2
    exit 1
}
sw-cli --session smoke-cut-failure document close --discard --json

sw-cli document inspect --json | jq -e --arg id "${created_b_id}" \
    '.document.document_id == $id and .document.current == true' >/dev/null || {
    echo "Independent reopen session changed the original session current" >&2
    exit 1
}
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

# Reuse SWCLI's protocol gate through the Linux CLI entry point. Extra native
# models/evidence stay outside the six published export artifacts.
dimension_outdir="$(mktemp -d "${SW_SMOKE_EVIDENCE_DIR:-/tmp}/swcli-driving.XXXXXX")"
# mktemp defaults to 0700; the host runner must be able to collect CI evidence.
chmod 755 "${dimension_outdir}"
PYTHONPATH="${SWCLI_SOURCE:-/opt/swcli/src}:${SWCLI_DEPS:-/opt/swcli-deps}/linux" \
    python3 /opt/swcli/scripts/ci/verify-driving-dimensions.py \
    --output-dir "${dimension_outdir}" \
    --host-output-dir "$(winepath -w "${dimension_outdir}")" \
    --cli-command /usr/local/bin/sw-cli

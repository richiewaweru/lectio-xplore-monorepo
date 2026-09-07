"""Typed prompt projections for shared preparation and teaching.

Projections are built from explicit allowlists. Sentinel tests insert unique
forbidden identifiers into excluded fields and assert they never appear in
serialized provider requests.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

# Native inventory that must never appear in shared prep / teaching packets.
_FORBIDDEN_NATIVE_KEYS = frozenset(
    {
        "allowed_components",
        "preferred_components",
        "component_selections",
        "components",
        "form_id",
        "object_id",
        "page_object",
        "valid_objects",
        "content_schema",
        "payload_schema",
        "capacity",
        "document_contract_version",
        "native_whole_lesson",
        "page_document_v2",
        "page_block_plans",
    }
)

_SHARED_PREP_ALLOWLIST = frozenset(
    {
        "concept_id",
        "title",
        "objective",
        "objective_hash",
        "primary_knowledge_type",
        "secondary_demand",
        "slots",
        "scope_contract",
        "prior_established",
        "prerequisites",
        "lesson_actuals",
        "external_prerequisites",
        "must_establish",
        "exclusions",
        "group_ids",
        "groups",
        "variant_previews",
        "shared_preparation",
        "repair",
    }
)

_SLOT_ALLOWLIST = frozenset(
    {
        "slot_id",
        "instance_id",
        "role",
        "purpose",
        "locked",
        "visual_required",
    }
)


class ProjectionLeakError(AssertionError):
    pass


def project_shared_preparation_packet(fixed_context: Mapping[str, Any]) -> dict[str, Any]:
    """Build the provider-facing Unit preparation packet (no native inventory)."""
    projected: dict[str, Any] = {"shared_preparation": True}
    for key in _SHARED_PREP_ALLOWLIST:
        if key == "shared_preparation":
            continue
        if key not in fixed_context:
            continue
        value = fixed_context[key]
        if key == "slots":
            projected[key] = [_project_slot(slot) for slot in (value or [])]
        elif key == "variant_previews":
            projected[key] = [
                _project_variant_preview(preview) for preview in (value or [])
            ]
        else:
            projected[key] = value
    assert_no_native_inventory(projected, where="shared preparation packet")
    return projected


def _project_slot(slot: Mapping[str, Any] | Any) -> dict[str, Any]:
    if hasattr(slot, "model_dump"):
        payload = slot.model_dump(mode="json")
    else:
        payload = dict(slot)
    return {key: payload[key] for key in _SLOT_ALLOWLIST if key in payload}


def _project_variant_preview(preview: Mapping[str, Any]) -> dict[str, Any]:
    slots = preview.get("slots") or []
    return {
        "group_profile": preview.get("group_profile"),
        "slots": [_project_slot(slot) for slot in slots],
        "toggles_applied": list(preview.get("toggles_applied") or []),
    }


def serialize_provider_request(
    *,
    system_prompt: str,
    user_payload: Mapping[str, Any],
) -> str:
    """Canonical serialization inspected by sentinel leakage tests."""
    return json.dumps(
        {"system_prompt": system_prompt, "user_payload": user_payload},
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )


def assert_no_native_inventory(payload: Any, *, where: str) -> None:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    leaks = sorted(
        key for key in _FORBIDDEN_NATIVE_KEYS if f'"{key}"' in serialized or f"'{key}'" in serialized
    )
    # Also reject hyphenated page-object / interaction markers when present as keys.
    if leaks:
        raise ProjectionLeakError(f"{where} leaked native keys: {leaks}")


def assert_sentinels_absent(
    serialized_request: str,
    sentinels: Sequence[str],
    *,
    where: str,
) -> None:
    found = [token for token in sentinels if token and token in serialized_request]
    if found:
        raise ProjectionLeakError(f"{where} leaked sentinel tokens: {found}")


def with_excluded_sentinels(
    context: Mapping[str, Any],
    *,
    sentinels: Mapping[str, Any],
) -> dict[str, Any]:
    """Attach forbidden fields solely for leakage tests (never projected)."""
    polluted = dict(context)
    polluted.update(sentinels)
    return polluted

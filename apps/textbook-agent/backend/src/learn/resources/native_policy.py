"""Learn native selection policy — consumer narrowing only (P04 / Phase G).

May offer/deny capabilities and budgets. Must not rewrite purpose, schemas or
evaluator semantics owned by retained interaction contracts.

Ordinary content generation is owned by the Learn document realizer (shared
document primitives). ``offered_content`` stays empty so legacy component ids
are not policy-admitted; writers still exist until Phase M hard-delete.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from learn.interactions.registry import (
    DELETED_INTERACTIONS,
    RETAINED_INTERACTIONS,
    RETIRED_ORDINARY_CONTENT_IDS,
)

LEARN_NATIVE_POLICY_BODY: dict[str, Any] = {
    "version": "1",
    "path": "learn",
    "selector": "content_interactions",
    "writer": "learn_components",
    # Document realizer is the production ordinary-content path (Phase E/F).
    # Keep empty until Phase M removes legacy content capability writers.
    "offered_content": [],
    # Policy-admitted interactions only (Phase G KEEP set).
    "offered_interactions": sorted(RETAINED_INTERACTIONS),
    "denied_capabilities": sorted(DELETED_INTERACTIONS | RETIRED_ORDINARY_CONTENT_IDS),
    "budgets": {
        "max_interactions_per_block": 1,
        "max_content_per_block": 1,
    },
    "require_assets_for": [
        "image-hotspot",
        "drag-label",
        "diagram-block",
        "image-block",
    ],
}


def default_learn_policy() -> dict[str, Any]:
    return copy.deepcopy(LEARN_NATIVE_POLICY_BODY)


def _hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def policy_version_and_hash(policy: dict[str, Any] | None = None) -> tuple[str, str]:
    body = policy if policy is not None else default_learn_policy()
    return str(body.get("version") or "1"), _hash(body)


def offered_capability_ids(policy: dict[str, Any] | None = None) -> frozenset[str]:
    body = policy if policy is not None else default_learn_policy()
    denied = {str(item) for item in (body.get("denied_capabilities") or [])}
    content = {str(item) for item in (body.get("offered_content") or [])}
    interactions = {str(item) for item in (body.get("offered_interactions") or [])}
    return frozenset((content | interactions) - denied)


def offered_content_ids(policy: dict[str, Any] | None = None) -> frozenset[str]:
    body = policy if policy is not None else default_learn_policy()
    denied = {str(item) for item in (body.get("denied_capabilities") or [])}
    return frozenset(str(item) for item in (body.get("offered_content") or [])) - denied


def offered_interaction_ids(policy: dict[str, Any] | None = None) -> frozenset[str]:
    body = policy if policy is not None else default_learn_policy()
    denied = {str(item) for item in (body.get("denied_capabilities") or [])}
    return (
        frozenset(str(item) for item in (body.get("offered_interactions") or [])) - denied
    )


def capabilities_requiring_assets(policy: dict[str, Any] | None = None) -> frozenset[str]:
    body = policy if policy is not None else default_learn_policy()
    return frozenset(str(item) for item in (body.get("require_assets_for") or []))


__all__ = [
    "LEARN_NATIVE_POLICY_BODY",
    "capabilities_requiring_assets",
    "default_learn_policy",
    "offered_capability_ids",
    "offered_content_ids",
    "offered_interaction_ids",
    "policy_version_and_hash",
]

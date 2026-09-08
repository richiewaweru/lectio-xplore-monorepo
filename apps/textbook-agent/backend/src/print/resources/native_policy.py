"""Print native selection policy — consumer narrowing only (P04).

May offer/deny forms, set budgets and asset rules. Must not rewrite purpose,
schemas or evaluator semantics owned by @lectio/page.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

# Default admission policy. Changing offered_forms / denied_forms / budgets
# changes eligibility without editing page-object definitions or selector branches.
PRINT_NATIVE_POLICY_BODY: dict[str, Any] = {
    "version": "1",
    "path": "print",
    "selector": "page_forms",
    "writer": "page_objects",
    # Closed offer set. Empty means "all package-compatible forms".
    "offered_forms": [
        "prose",
        "list",
        "table",
        "figure",
        "aside",
        "worked-example",
        "questions",
        "choices",
    ],
    "denied_forms": ["heading", "answer-key"],
    "budgets": {
        "max_forms_per_block": 1,
        "max_figures_per_lesson": 4,
    },
    "require_assets_for": ["figure"],
}


def default_print_policy() -> dict[str, Any]:
    return copy.deepcopy(PRINT_NATIVE_POLICY_BODY)


def _hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def policy_version_and_hash(policy: dict[str, Any] | None = None) -> tuple[str, str]:
    body = policy if policy is not None else default_print_policy()
    return str(body.get("version") or "1"), _hash(body)


def offered_form_ids(policy: dict[str, Any] | None = None) -> frozenset[str]:
    body = policy if policy is not None else default_print_policy()
    denied = {str(item) for item in (body.get("denied_forms") or [])}
    offered = body.get("offered_forms")
    if offered is None:
        return frozenset()
    if not offered:
        # Explicit empty offer → fail closed (no silent catalogue widen).
        return frozenset()
    return frozenset(str(item) for item in offered) - denied


def forms_requiring_assets(policy: dict[str, Any] | None = None) -> frozenset[str]:
    body = policy if policy is not None else default_print_policy()
    return frozenset(str(item) for item in (body.get("require_assets_for") or []))


__all__ = [
    "PRINT_NATIVE_POLICY_BODY",
    "default_print_policy",
    "forms_requiring_assets",
    "offered_form_ids",
    "policy_version_and_hash",
]

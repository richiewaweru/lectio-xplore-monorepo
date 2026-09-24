"""Canonical identity and source-lineage checks for shared lesson artifacts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

def _json_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def canonical_shared_lesson_payload(document: Any) -> dict[str, Any]:
    """Return learner meaning and source lineage, excluding artifact metadata."""
    data = _json_value(document)
    # Normalize mapping inputs through the same closed nested contracts used by
    # the document model, so omitted defaults cannot produce a stale digest.
    from document.shared_lesson.models import FrozenSharedTaskSpec, SharedProvenance, SharedSection

    sections = [
        _json_value(SharedSection.model_validate(section)) for section in data.get("sections", [])
    ]
    tasks = [
        _json_value(FrozenSharedTaskSpec.model_validate(task)) for task in data.get("tasks", [])
    ]
    provenance = _json_value(SharedProvenance.model_validate(data.get("provenance", {})))
    return {
        "schema_version": data["schema_version"],
        "teaching_plan_id": data["teaching_plan_id"],
        "teaching_plan_revision": data["teaching_plan_revision"],
        "teaching_plan_hash": data["teaching_plan_hash"],
        "title": data["title"],
        "sections": sections,
        "tasks": tasks,
        "provenance": provenance,
    }


def shared_lesson_content_hash(document: Any) -> str:
    canonical = json.dumps(
        canonical_shared_lesson_payload(document),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_shared_lesson_source(
    document: Any,
    *,
    teaching_plan_id: str,
    teaching_plan_revision: int,
    teaching_plan_hash: str,
) -> None:
    """Reject a consumer whose expected approved source identity differs."""
    mismatches = []
    for field, expected in (
        ("teaching_plan_id", teaching_plan_id),
        ("teaching_plan_revision", teaching_plan_revision),
        ("teaching_plan_hash", teaching_plan_hash),
    ):
        actual = getattr(document, field)
        if actual != expected:
            mismatches.append(field)
    if mismatches:
        raise ValueError("shared lesson source identity mismatch: " + ", ".join(mismatches))
    actual_hash = shared_lesson_content_hash(document)
    if actual_hash != document.content_hash:
        raise ValueError("shared lesson content hash mismatch")


__all__ = [
    "canonical_shared_lesson_payload",
    "shared_lesson_content_hash",
    "verify_shared_lesson_source",
]

"""Assemble LearnDocument v2 from ordered authored nodes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from learn.contracts.lesson_document import assert_valid_learn_document


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def assemble_learn_document(
    nodes: Sequence[Mapping[str, Any]],
    meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a LearnDocument v2 dict from ordered node payloads.

    Preserves ``teaching_block_id`` provenance already present on nodes.
    ``meta`` supplies document identity fields (title, subject, source, …).
    """
    info = dict(meta or {})
    now = _utc_now_iso()
    document: dict[str, Any] = {
        "version": 2,
        "id": str(info.get("id") or _new_id("lesson")),
        "title": str(info.get("title") or "Learn lesson"),
        "subject": str(info.get("subject") or "general"),
        "source": str(info.get("source") or "generated"),
        "source_generation_id": info.get("source_generation_id"),
        "nodes": [dict(node) for node in nodes],
        "created_at": str(info.get("created_at") or now),
        "updated_at": str(info.get("updated_at") or now),
        "teaching_plan_id": info.get("teaching_plan_id"),
        "teaching_plan_revision": info.get("teaching_plan_revision"),
        "sections": [dict(section) for section in (info.get("sections") or [])],
    }
    # Drop explicit nulls for optional provenance only when caller omitted keys.
    if "teaching_plan_id" not in info:
        document["teaching_plan_id"] = None
    if "teaching_plan_revision" not in info:
        document["teaching_plan_revision"] = None
    if "source_generation_id" not in info:
        document["source_generation_id"] = None

    assert_valid_learn_document(document)
    return document


__all__ = ["assemble_learn_document"]

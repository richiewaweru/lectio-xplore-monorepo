"""Detect native whole-lesson generations and block legacy stage2 paths."""

from __future__ import annotations

import json
from typing import Any, Mapping

from core.database.models import GenerationModel
from planning.whole_lesson.states import NATIVE_STATUSES


def _as_mapping(raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}


def _document_contract_version(generation: GenerationModel | None) -> int:
    if generation is None:
        return 1
    plan = _as_mapping(getattr(generation, "planning_spec_json", None))
    try:
        return int(plan.get("document_contract_version") or 1)
    except (TypeError, ValueError):
        return 1


def generation_is_native_whole_lesson(
    state: Mapping[str, Any] | None = None,
    generation: GenerationModel | None = None,
) -> bool:
    """True when this generation must use the native v2 whole-lesson path."""
    chunked = dict(state or {})
    if not chunked and generation is not None:
        chunked = _as_mapping(getattr(generation, "chunked_state_json", None))

    context = chunked.get("context")
    if isinstance(context, Mapping) and context.get("native_whole_lesson"):
        return True
    if chunked.get("page_document_v2"):
        return True
    if chunked.get("native_whole_lesson"):
        return True
    if _document_contract_version(generation) >= 2:
        return True
    if generation is not None:
        status = str(getattr(generation, "status", "") or "")
        if status in NATIVE_STATUSES:
            return True
    stage = str(chunked.get("stage") or "")
    if stage in NATIVE_STATUSES:
        return True
    return False

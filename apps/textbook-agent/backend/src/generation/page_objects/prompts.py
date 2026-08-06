"""Writer prompt builders for native page-object generation and repair."""

from __future__ import annotations

import json
from typing import Any

from generation.page_objects.models import WriterContext

_WRITER_SYSTEM = """You write one already-planned educational page object.

You may not change:
- block ID;
- section ID;
- position;
- pedagogical intent;
- requested object type;
- lesson objective;
- scope restrictions.

Your output is the content object only. It must validate against the supplied form schema. Do not wrap it in markdown, explanation, or an object-name envelope.

Respect:
- grade level;
- terminology;
- must-not-introduce constraints;
- neighboring block summaries;
- the specific pedagogical intent;
- the block brief.

Do not invent answers inside student question content. Assessment answers are returned only through the assessment bundle contract.

Return JSON only for the selected content schema.
"""

_REPAIR_SYSTEM = """Correct a previously invalid page-object content response. Do not redesign the block and do not change its object, intent, ID, or educational purpose.

Return the complete corrected JSON content object only.

Fix every listed validation error while preserving correct content from the previous response. Do not add properties outside the schema. Do not include markdown fences or commentary.
"""


def _contract_payload(contract: Any) -> dict[str, Any]:
    if contract is None:
        return {}
    if hasattr(contract, "to_dict"):
        return dict(contract.to_dict())
    if isinstance(contract, dict):
        return dict(contract)
    return {"value": str(contract)}


def build_writer_prompt(ctx: WriterContext, contract: Any) -> str:
    prev_brief = ctx.neighbour_summaries[0] if len(ctx.neighbour_summaries) > 0 else ""
    next_brief = ctx.neighbour_summaries[1] if len(ctx.neighbour_summaries) > 1 else ""
    payload = {
        "lesson_context": ctx.lesson_context or {},
        "section_context": {"section_id": ctx.section_id} if ctx.section_id else {},
        "block": {
            "id": ctx.planned.id,
            "position": ctx.planned.position,
            "intent": ctx.planned.intent,
            "object": ctx.planned.object,
            "brief": ctx.planned.brief,
            "placement": getattr(ctx.planned, "placement", "main"),
        },
        "neighbours": {"before": prev_brief, "after": next_brief},
        "writer_contract": _contract_payload(contract),
        "terminology": list(ctx.terminology),
    }
    return (
        f"{_WRITER_SYSTEM}\n\n## INPUT JSON\n"
        f"{json.dumps(payload, indent=2, sort_keys=True)}"
    )


def build_repair_prompt(
    ctx: WriterContext,
    previous_output: object,
    validation_errors: list[dict[str, Any]],
    contract: Any,
) -> str:
    payload = {
        "requested_object": ctx.planned.object,
        "block_id": ctx.planned.id,
        "intent": ctx.planned.intent,
        "original_brief": ctx.planned.brief,
        "writer_contract": _contract_payload(contract),
        "previous_invalid_output": previous_output,
        "validation_errors": [
            {"path": str(err.get("path", "")), "message": str(err.get("message", ""))}
            for err in validation_errors
        ],
    }
    return (
        f"{_REPAIR_SYSTEM}\n\n## REPAIR PAYLOAD\n"
        f"{json.dumps(payload, indent=2, sort_keys=True, default=str)}"
    )

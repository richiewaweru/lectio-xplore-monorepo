"""Map shared document.writer nodes onto Print page-object content."""

from __future__ import annotations

import logging
from typing import Any, Mapping

from document.models import DOCUMENT_PRIMITIVE_KINDS
from document.writer import write_document_primitive
from print.generation.document_form_map import PRINT_OBJECT_TO_PRIMITIVE
from print.rendering.page_objects.models import WriterContext, WriterOutcome
from print.rendering.page_objects.validation import UnsupportedObject

logger = logging.getLogger(__name__)


def document_node_to_print_content(object_id: str, node: Mapping[str, Any]) -> dict[str, Any]:
    kind = str(node.get("kind") or "")
    if object_id == "prose" or kind == "paragraph" or kind == "heading":
        text = str(node.get("text") or "").strip()
        return {"paragraphs": [text or " "]}
    if object_id == "list" or kind == "list":
        items = [{"text": str(item)} for item in (node.get("items") or []) if str(item).strip()]
        if not items:
            items = [{"text": str(node.get("text") or "Item")}]
        style = "ordered" if node.get("ordered") else "unordered"
        return {"style": style, "items": items}
    if object_id == "table" or kind == "table":
        headers = [str(h) for h in (node.get("headers") or [])]
        if not headers:
            headers = ["item"]
        columns = [{"id": f"c{index}", "label": label} for index, label in enumerate(headers)]
        rows = []
        for raw_row in node.get("rows") or []:
            cells: dict[str, str] = {}
            values = list(raw_row) if isinstance(raw_row, (list, tuple)) else [raw_row]
            for index, column in enumerate(columns):
                cells[column["id"]] = str(values[index]) if index < len(values) else ""
            rows.append({"cells": cells})
        if not rows:
            rows = [{"cells": {columns[0]["id"]: ""}}]
        return {
            "columns": columns,
            "rows": rows,
            "caption": str(node.get("caption") or "") or None,
            "presentation": "standard",
        }
    if object_id == "aside" or kind == "callout":
        title = str(node.get("title") or node.get("tone") or "Note")
        body = str(node.get("body") or node.get("text") or "").strip()
        return {"label": title[:80] or "Note", "body": body or title}
    if object_id == "figure" or kind == "figure":
        caption = str(node.get("caption") or "").strip()
        alt = str(node.get("alt") or caption or "Figure").strip()
        return {"caption": caption or alt, "alt_text": alt}
    raise UnsupportedObject(object_id)


async def write_ordinary_via_shared_writer(
    ctx: WriterContext,
    *,
    provider: Any | None = None,
) -> WriterOutcome:
    """Author ordinary Print content through document.writer, then map to page objects."""
    object_id = ctx.planned.object
    kind = PRINT_OBJECT_TO_PRIMITIVE.get(object_id)
    if kind not in DOCUMENT_PRIMITIVE_KINDS:
        raise UnsupportedObject(object_id)

    from infra.authoring import LLMAuthoringProvider
    from print.rendering.page_objects.registry import (
        _authoring_provider,
        _figure_result_from_content,
    )
    from print.rendering.page_objects.validation import validate_content

    authoring = _authoring_provider(provider, ctx=ctx) or LLMAuthoringProvider()
    logger.info(
        "PRINT_SHARED_WRITER document.writer object=%s block=%s",
        object_id,
        ctx.planned.id,
    )
    lesson_context = dict(ctx.lesson_context or {})
    teaching_block = {
        "id": ctx.planned.id,
        "intent": getattr(ctx.planned, "intent", "") or "",
        "brief": ctx.planned.brief,
        "evidence": getattr(ctx.planned, "evidence", "") or "",
    }
    node = await write_document_primitive(
        kind=kind,
        brief=ctx.planned.brief,
        teaching_block=teaching_block,
        lesson_context=lesson_context,
        terminology=list(ctx.terminology),
        allowed_facts=list(lesson_context.get("allowed_facts") or []),
        teaching_block_id=ctx.planned.id,
        provider=authoring,
    )
    content = document_node_to_print_content(object_id, node)
    if object_id == "figure":
        return _figure_result_from_content(ctx, content)
    validated = validate_content(object_id, content)
    return WriterOutcome(block_id=ctx.planned.id, content=validated, status="ready")


__all__ = [
    "document_node_to_print_content",
    "write_ordinary_via_shared_writer",
]

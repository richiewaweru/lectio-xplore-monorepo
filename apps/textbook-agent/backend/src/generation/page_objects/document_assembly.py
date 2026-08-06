"""Assemble and persist LectioDocumentV2 without legacy SectionContent."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any
from uuid import uuid4

from contracts.lectio_page import validate_document
from generation.page_objects import WriterContext, WriterResult, dispatch_writer
from v3_blueprint.planning.models import PlannedBlock, SectionBlockPlan


class DocumentAssemblyError(ValueError):
    pass


def normalize_block_positions(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for index, block in enumerate(blocks):
        item = dict(block)
        item["position"] = index
        out.append(item)
    return out


def assemble_section(
    *,
    section_id: str,
    title: str,
    plan: SectionBlockPlan,
    writer_results: list[WriterResult],
) -> dict[str, Any]:
    by_id = {result.block_id: result for result in writer_results}
    blocks: list[dict[str, Any]] = []
    for planned in plan.blocks:
        result = by_id.get(planned.id)
        if result is None:
            raise DocumentAssemblyError(f"missing writer result for block {planned.id}")
        if result.object != planned.object or result.intent != planned.intent:
            raise DocumentAssemblyError("writer result diverged from plan")
        block = {
            "id": planned.id,
            "object": planned.object,
            "intent": planned.intent,
            "position": planned.position,
            "content": result.content,
            "layout": {"placement": planned.placement},
        }
        if planned.role:
            block["role"] = planned.role
        blocks.append(block)
    return {
        "id": section_id,
        "title": title,
        "blocks": normalize_block_positions(blocks),
    }


def assemble_document_v2(
    *,
    title: str,
    sections: list[dict[str, Any]],
    document_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    doc = {
        "document_version": 2,
        "contract_version": "1.0.0",
        "id": document_id or f"doc-{uuid4().hex[:12]}",
        "title": title,
        "language": "en",
        "metadata": metadata
        or {
            "catalogue_version": "1.1.0",
            "resource_type": "lesson",
        },
        "sections": sections,
    }
    errors = validate_document(doc)
    if errors:
        raise DocumentAssemblyError("; ".join(errors[:8]))
    return doc


def write_planned_section(
    *,
    section_id: str,
    title: str,
    plan: SectionBlockPlan,
    item_records: tuple[dict[str, Any], ...] = (),
) -> tuple[dict[str, Any], list[WriterResult]]:
    results = [
        dispatch_writer(WriterContext(planned=block, item_records=item_records))
        for block in plan.blocks
    ]
    section = assemble_section(
        section_id=section_id, title=title, plan=plan, writer_results=results
    )
    return section, results


def canonical_document_sha256(document: dict[str, Any]) -> str:
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def persist_document_json(
    existing: dict[str, Any] | None,
    document: dict[str, Any],
) -> dict[str, Any]:
    """Persist into GenerationModel.document_json-compatible envelope.

    Additive: stores v2 document under document_json while preserving unrelated keys.
    Does not construct legacy SectionContent.
    """
    envelope = deepcopy(existing) if existing else {}
    if "SectionContent" in json.dumps(document):
        raise DocumentAssemblyError("v2 document must not embed SectionContent")
    envelope["document_version"] = 2
    envelope["lectio_document"] = document
    envelope["kind"] = envelope.get("kind") or "v3_booklet_pack"
    return envelope


def reload_document(envelope: dict[str, Any]) -> dict[str, Any]:
    doc = envelope.get("lectio_document")
    if not isinstance(doc, dict):
        raise DocumentAssemblyError("envelope missing lectio_document")
    # Normalize on reload for stable equality
    sections = []
    for section in doc.get("sections", []):
        item = dict(section)
        item["blocks"] = normalize_block_positions(list(item.get("blocks") or []))
        sections.append(item)
    reloaded = dict(doc)
    reloaded["sections"] = sections
    errors = validate_document(reloaded)
    if errors:
        raise DocumentAssemblyError("; ".join(errors[:8]))
    return reloaded

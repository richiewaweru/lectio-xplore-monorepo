"""Assemble and persist LectioDocumentV2 without legacy SectionContent."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any
from uuid import uuid4

from contracts.lectio_page import validate_document
from generation.page_objects.models import WriterContext, WriterOutcome
from generation.page_objects.registry import dispatch_writer
from generation.page_objects.validation import validate_answer_key_integrity
from v3_blueprint.planning.models import SectionBlockPlan


class DocumentAssemblyError(ValueError):
    pass


def normalize_block_positions(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for index, block in enumerate(blocks):
        item = dict(block)
        item["position"] = index
        out.append(item)
    return out


def collect_answer_entries(writer_results: list[WriterOutcome]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for result in writer_results:
        for entry in result.answer_entries:
            entries.append(dict(entry))
    return entries


def build_answer_key_block(
    *,
    document_id: str,
    answer_entries: list[dict[str, Any]],
    group_title: str | None = None,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for raw in answer_entries:
        entry: dict[str, Any] = {
            "question_id": str(raw["question_id"]),
            "answer": raw["answer"],
        }
        if raw.get("alternatives"):
            entry["alternatives"] = list(raw["alternatives"])
        if "working" in raw:
            entry["working"] = raw.get("working")
        if "rubric" in raw:
            entry["rubric"] = raw.get("rubric")
        entries.append(entry)
    group: dict[str, Any] = {"entries": entries}
    if group_title:
        group["title"] = group_title
    return {
        "id": f"answer-key-{document_id}",
        "object": "answer-key",
        "intent": "answer-key",
        "position": 0,
        "content": {"groups": [group]},
    }


def assemble_section(
    *,
    section_id: str,
    title: str,
    plan: SectionBlockPlan,
    writer_results: list[WriterOutcome],
) -> dict[str, Any]:
    by_id = {result.block_id: result for result in writer_results}
    blocks: list[dict[str, Any]] = []
    for planned in plan.blocks:
        result = by_id.get(planned.id)
        if result is None:
            raise DocumentAssemblyError(f"missing writer result for block {planned.id}")
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
    answer_entries: list[dict[str, Any]] | None = None,
    writer_results: list[WriterOutcome] | None = None,
) -> dict[str, Any]:
    doc_id = document_id or f"doc-{uuid4().hex[:12]}"
    entries = list(answer_entries or [])
    if not entries and writer_results:
        entries = collect_answer_entries(writer_results)

    doc: dict[str, Any] = {
        "document_version": 2,
        "contract_version": "1.0.0",
        "id": doc_id,
        "title": title,
        "language": "en",
        "metadata": metadata
        or {
            "catalogue_version": "1.1.0",
            "resource_type": "lesson",
        },
        "sections": sections,
    }

    if entries:
        blocks = [
            block
            for section in sections
            for block in (section.get("blocks") or [])
        ]
        try:
            validate_answer_key_integrity(blocks, entries)
        except ValueError as exc:
            raise DocumentAssemblyError(str(exc)) from exc
        doc["answer_key"] = build_answer_key_block(
            document_id=doc_id,
            answer_entries=entries,
        )

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
) -> tuple[dict[str, Any], list[WriterOutcome]]:
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
        normalized_blocks = normalize_block_positions(list(item.get("blocks") or []))
        for block in normalized_blocks:
            if block.get("object") != "figure":
                continue
            content = dict(block.get("content") or {})
            asset = dict(content.get("asset") or {})
            # Older visual callbacks persisted optional URL fields as JSON null
            # and topology recovery once persisted audit-only keys alongside
            # the renderable asset. The page contract permits omission, not
            # null or arbitrary metadata; normalize those legacy fields on
            # reload so a restarted worker can attach the next success.
            for optional_key in ("src", "svg", "sha256", "asset_key"):
                if asset.get(optional_key) is None:
                    asset.pop(optional_key, None)
            for audit_key in ("sha256", "asset_key"):
                asset.pop(audit_key, None)
            content["asset"] = asset
            block["content"] = content
        item["blocks"] = normalized_blocks
        sections.append(item)
    reloaded = dict(doc)
    reloaded["sections"] = sections
    errors = validate_document(reloaded)
    if errors:
        raise DocumentAssemblyError("; ".join(errors[:8]))
    return reloaded

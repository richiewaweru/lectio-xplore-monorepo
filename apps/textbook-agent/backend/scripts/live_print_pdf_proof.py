"""Live proof: Teaching Plan → Print composition → LLM content → PDF.

Ordinary content uses shared document writer. Print task treatments use
deterministic response shells (questions/choices) with learner-facing stems
authored via the document writer as prose instructions when needed.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path

from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from document.writer import write_document_primitive
from infra.authoring import LLMAuthoringProvider
from print.generation.composition_bridge import build_print_production_from_composition
from print.generation.document_form_map import PRIMITIVE_TO_PRINT_OBJECT
from print.rendering.page_objects.views import render_document_pdf

EVIDENCE_DIR = (
    Path(__file__).resolve().parents[4]
    / "docs"
    / "document-overhaul"
    / "reports"
    / "evidence"
)


def _plan() -> TeachingPlan:
    return TeachingPlan(
        teaching_plan_id=f"tp-live-print-pdf-{uuid.uuid4().hex[:8]}",
        revision=1,
        arc="Students explain why plants need light to make food.",
        sections=[
            TeachingPlanSection(
                slot_id="orient",
                specific_purpose="orient",
                blocks=[
                    TeachingPlanBlock(
                        id="orient-b1",
                        position=0,
                        intent="introduce",
                        brief=(
                            "Orient with the covered-leaf plant anchor. "
                            "State that light is required for food-making."
                        ),
                        evidence="Learner names light as required.",
                        evidence_refs=[],
                    )
                ],
            ),
            TeachingPlanSection(
                slot_id="explain",
                specific_purpose="explain",
                blocks=[
                    TeachingPlanBlock(
                        id="explain-b1",
                        position=0,
                        intent="explain",
                        brief=(
                            "Explain photosynthesis at Grade 4: leaves use light "
                            "to make sugar from water and carbon dioxide."
                        ),
                        evidence="Learner explains light → food.",
                        evidence_refs=[],
                    )
                ],
            ),
            TeachingPlanSection(
                slot_id="check",
                specific_purpose="check",
                blocks=[
                    TeachingPlanBlock(
                        id="check-b1",
                        position=0,
                        intent="check",
                        brief="Check understanding: why a covered leaf cannot make food.",
                        evidence="Correct option selected.",
                        evidence_refs=[],
                        learner_action=LearnerActionBrief(
                            action="select-one",
                            target="covered leaf cannot make food",
                            purpose="check understanding",
                            expected_evidence="correct option",
                            difficulty="guided",  # type: ignore[arg-type]
                        ),
                        source_question_ids=["q-covered-1"],
                    )
                ],
            ),
        ],
    )


async def _write_ordinary(
    *,
    kind: str,
    block: TeachingPlanBlock,
    provider: LLMAuthoringProvider,
    lesson_ctx: dict,
) -> dict:
    # Print FormPlan collapses heading → prose.
    write_kind = "paragraph" if kind == "heading" else kind
    if write_kind not in {
        "paragraph",
        "heading",
        "list",
        "figure",
        "table",
        "callout",
    }:
        write_kind = "paragraph"
    node = await write_document_primitive(
        kind=write_kind,
        brief=block.brief or "",
        teaching_block={
            "id": block.id,
            "intent": block.intent,
            "brief": block.brief,
            "evidence": block.evidence,
        },
        lesson_context=lesson_ctx,
        evidence=block.evidence,
        teaching_block_id=block.id,
        provider=provider,
    )
    if write_kind == "paragraph":
        return {"paragraphs": [str(node.get("text") or "")]}
    if write_kind == "list":
        return {
            "style": "ordered" if node.get("ordered") else "unordered",
            "items": [{"text": str(i)} for i in (node.get("items") or [])],
        }
    if write_kind == "table":
        headers = [str(h) for h in (node.get("headers") or [])]
        rows = node.get("rows") or []
        columns = [{"id": f"c{i}", "label": h} for i, h in enumerate(headers)]
        out_rows = []
        for row in rows:
            cells = {}
            for i, cell in enumerate(row if isinstance(row, list) else []):
                key = columns[i]["id"] if i < len(columns) else f"c{i}"
                cells[key] = str(cell)
            out_rows.append({"cells": cells})
        return {"columns": columns, "rows": out_rows, "caption": node.get("caption")}
    if write_kind == "callout":
        return {
            "label": node.get("title") or "Note",
            "body": str(node.get("body") or ""),
        }
    if write_kind == "figure":
        return {
            "caption": str(node.get("caption") or ""),
            "alt_text": str(node.get("alt") or ""),
            "asset": {"status": "pending"},
        }
    return {"paragraphs": [str(node.get("text") or block.brief or "")]}


async def main() -> int:
    provider = LLMAuthoringProvider(node_name="v3_block_writer_fast")
    plan = _plan()
    form_plan, snapshot, composition = await build_print_production_from_composition(
        teaching_plan=plan,
        provider=provider,
    )
    blocks_by_id = {b.id: b for s in plan.sections for b in s.blocks}
    lesson_ctx = {
        "title": plan.arc,
        "objective": plan.arc,
        "subject": "science",
        "teaching_plan_revision": plan.revision,
    }

    sections_out: list[dict] = []
    for section in form_plan.sections:
        written_blocks: list[dict] = []
        for decision in section.forms:
            block = blocks_by_id.get(decision.block_id)
            if block is None:
                continue
            object_id = str(decision.object)
            if object_id in {"choices", "questions", "worked-example"}:
                # Print-only treatment: write a stem paragraph, then attach
                # response surface metadata (ruled/response areas are Print-owned).
                stem = await write_document_primitive(
                    kind="paragraph",
                    brief=block.brief or "",
                    teaching_block={
                        "id": block.id,
                        "intent": block.intent,
                        "brief": block.brief,
                        "evidence": block.evidence,
                    },
                    lesson_context=lesson_ctx,
                    evidence=block.evidence,
                    teaching_block_id=block.id,
                    provider=provider,
                )
                if object_id == "choices":
                    content = {
                        "instructions": str(stem.get("text") or ""),
                        "items": [
                            {
                                "prompt": str(stem.get("text") or ""),
                                "options": ["Needs light", "Needs darkness", "Needs only water"],
                                "correct_index": 0,
                            }
                        ],
                    }
                else:
                    content = {
                        "instructions": str(stem.get("text") or ""),
                        "items": [{"prompt": str(stem.get("text") or ""), "lines": 4}],
                    }
            else:
                # Invert print object → primitive for writer
                primitive = next(
                    (k for k, v in PRIMITIVE_TO_PRINT_OBJECT.items() if v == object_id),
                    "paragraph",
                )
                if object_id == "prose":
                    primitive = "paragraph"
                if object_id == "aside":
                    primitive = "callout"
                content = await _write_ordinary(
                    kind=primitive,
                    block=block,
                    provider=provider,
                    lesson_ctx=lesson_ctx,
                )
            written_blocks.append(
                {"id": block.id, "object": object_id, "content": content}
            )
        sections_out.append(
            {"id": section.slot_id, "title": section.slot_id, "blocks": written_blocks}
        )

    generation_id = f"print-out-{uuid.uuid4().hex[:12]}"
    doc = {
        "id": generation_id,
        "title": plan.arc or "Print lesson",
        "subject": "science",
        "sections": sections_out,
        "teaching_plan_id": plan.teaching_plan_id,
        "teaching_plan_hash": getattr(snapshot, "teaching_plan_hash", None),
        "composition_plan": composition.model_dump(mode="json"),
    }

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = EVIDENCE_DIR / f"{generation_id}.pdf"
    json_path = EVIDENCE_DIR / f"{generation_id}.json"
    render_document_pdf(doc, pdf_path, audience="student")
    size = pdf_path.stat().st_size if pdf_path.exists() else 0
    # Reload: re-read PDF bytes
    reloaded_size = pdf_path.read_bytes().__len__() if pdf_path.exists() else 0
    json_path.write_text(
        json.dumps(
            {
                "generation_id": generation_id,
                "pdf_path": str(pdf_path),
                "pdf_bytes": size,
                "reloaded_bytes": reloaded_size,
                "form_objects": [f.object for s in form_plan.sections for f in s.forms],
                "lanes": [d.lane for d in composition.decisions],
                "kinds": [d.kind for d in composition.decisions],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    form_objects = [f.object for s in form_plan.sections for f in s.forms]
    print("LIVE_PRINT_PDF generation_id=", generation_id)
    print("LIVE_PRINT_PDF pdf_path=", pdf_path)
    print("LIVE_PRINT_PDF pdf_bytes=", size)
    print("LIVE_PRINT_PDF form_objects=", json.dumps(form_objects))

    if size < 500 or reloaded_size != size:
        print("LIVE_PRINT_PDF=FAIL pdf missing or reload mismatch", file=sys.stderr)
        return 1
    if "choices" not in form_objects and "questions" not in form_objects:
        print("LIVE_PRINT_PDF=FAIL missing print task treatment", file=sys.stderr)
        return 1

    print("LIVE_PRINT_PDF=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

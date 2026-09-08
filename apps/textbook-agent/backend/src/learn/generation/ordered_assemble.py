"""Deterministic ordered Learn document assembly (P06).

Preserves teaching order, repeated component types, and content→activity→content
interleaving via authoritative ``block_ids``. Does not collapse into a wide
SectionContent object.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from curriculum.teaching_plan.models import TeachingPlan
from learn.generation.interaction_writer import (
    InteractionWriterError,
    write_interaction_from_work_order,
)
from learn.generation.native_selection import LearnSelectionSnapshot
from learn.generation.work_orders import LearnWorkOrder, compile_learn_work_orders


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _content_block_from_decision(
    *,
    block_id: str,
    content_id: str,
    brief: str,
    position: int,
) -> dict[str, Any]:
    """Minimal validated content payload for assembly fixtures / native assemble."""
    # Map common content ids to a body-bearing shape the student shell can render.
    if content_id in {"explanation-block", "callout", "key-concept", "summary-block"}:
        content: dict[str, Any] = {"body": brief or "Content"}
        if content_id == "explanation-block":
            content = {"body": brief or "Content", "callouts": []}
        return {
            "id": _new_id("blk"),
            "component_id": content_id if content_id != "key-concept" else "key-fact",
            "position": position,
            "content": content if content_id != "key-concept" else {"statement": brief or "Key idea"},
        }
    if content_id == "section-header":
        return {
            "id": _new_id("blk"),
            "component_id": "section-header",
            "position": position,
            "content": {"title": brief or "Section", "subtitle": ""},
        }
    if content_id == "hook-hero":
        return {
            "id": _new_id("blk"),
            "component_id": "hook-hero",
            "position": position,
            "content": {
                "type": "prose",
                "headline": brief[:80] or "Hook",
                "body": brief or "Hook body",
                "anchor": block_id,
            },
        }
    # Generic fallback: explanation-shaped body under the selected component id.
    return {
        "id": _new_id("blk"),
        "component_id": content_id,
        "position": position,
        "content": {"body": brief or "Content"},
    }


def _interaction_block(
    *,
    contract: Mapping[str, Any],
    position: int,
) -> dict[str, Any]:
    return {
        "id": _new_id("blk"),
        "component_id": f"learn-interaction:{contract['kind']}",
        "position": position,
        "content": {
            "prompt": contract.get("prompt"),
            "kind": contract.get("kind"),
        },
        "learn_interaction": dict(contract),
        "assessment_mode": contract.get("assessment_mode"),
        "concept_refs": list(contract.get("concept_refs") or []),
    }


def assemble_ordered_learn_document(
    *,
    teaching_plan: TeachingPlan,
    snapshot: LearnSelectionSnapshot,
    work_orders: Sequence[LearnWorkOrder] | None = None,
    interaction_payloads: Mapping[str, Mapping[str, Any]] | None = None,
    content_overrides: Mapping[str, Mapping[str, Any]] | None = None,
    title: str | None = None,
    subject: str = "general",
    preset_id: str = "blue-classroom",
    lesson_id: str | None = None,
    source: str = "generated",
    source_generation_id: str | None = None,
    write_interactions: bool = True,
    approved_items: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Assemble a LessonDocument whose ``block_ids`` are the authority for order.

    When ``write_interactions`` is true, interaction work orders are executed
    through the normal writer (not injected). Pass ``interaction_payloads`` keyed
    by work_order_id only for replay of already-written payloads.
    """
    orders = list(work_orders) if work_orders is not None else compile_learn_work_orders(
        teaching_plan=teaching_plan,
        snapshot=snapshot,
        approved_items=approved_items,
    )
    orders_by_block: dict[str, list[LearnWorkOrder]] = {}
    for order in orders:
        orders_by_block.setdefault(order.block_id, []).append(order)

    written = dict(interaction_payloads or {})
    if write_interactions:
        for order in orders:
            if order.lane != "interaction":
                continue
            if order.work_order_id in written:
                continue
            _, _, payload = write_interaction_from_work_order(
                order,
                approved_items=approved_items,
            )
            written[order.work_order_id] = payload

    blocks: dict[str, dict[str, Any]] = {}
    sections_out: list[dict[str, Any]] = []
    decision_by_block = {d.block_id: d for d in snapshot.decisions}

    for section in teaching_plan.sections:
        section_id = section.slot_id
        block_ids: list[str] = []
        position = 0
        for plan_block in section.blocks:
            decision = decision_by_block.get(plan_block.id)
            if decision is None:
                continue
            block_orders = orders_by_block.get(plan_block.id, [])
            # Emit content first, then interaction — preserves content→activity order.
            # Multiple decisions on the same teaching block stay in work-order order.
            content_order = next((o for o in block_orders if o.lane == "content"), None)
            interaction_order = next((o for o in block_orders if o.lane == "interaction"), None)

            if content_order is not None or decision.content_id:
                content_id = (content_order.capability_id if content_order else decision.content_id) or "explanation-block"
                override = (content_overrides or {}).get(plan_block.id)
                if override is not None:
                    block = {
                        "id": _new_id("blk"),
                        "component_id": str(override.get("component_id") or content_id),
                        "position": position,
                        "content": dict(override.get("content") or {"body": plan_block.brief}),
                    }
                else:
                    block = _content_block_from_decision(
                        block_id=plan_block.id,
                        content_id=content_id,
                        brief=plan_block.brief,
                        position=position,
                    )
                blocks[block["id"]] = block
                block_ids.append(block["id"])
                position += 1

            if interaction_order is not None or decision.interaction_id:
                if interaction_order is None:
                    raise InteractionWriterError(
                        "MISSING_INTERACTION_ORDER",
                        f"selection has interaction for {plan_block.id!r} but no work order",
                    )
                payload = written.get(interaction_order.work_order_id)
                if payload is None:
                    raise InteractionWriterError(
                        "MISSING_INTERACTION_PAYLOAD",
                        f"no payload for work order {interaction_order.work_order_id!r}",
                    )
                block = _interaction_block(contract=payload, position=position)
                blocks[block["id"]] = block
                block_ids.append(block["id"])
                position += 1

        sections_out.append(
            {
                "id": section_id,
                "template_id": "open-canvas",
                "title": section.specific_purpose or section_id,
                "position": len(sections_out),
                "block_ids": block_ids,
                "learner_label": section.slot_id,
                "learner_intent": section.slot_id if section.slot_id in {
                    "orient", "explain", "practice", "check", "reflect", "bridge"
                } else "explain",
                "required": True,
                "navigation_policy": "linear",
                "completion_policy": "submitted",
                "assessment_mode": "practice",
            }
        )

    now = _utc_now_iso()
    return {
        "version": 1,
        "id": lesson_id or _new_id("lesson"),
        "title": title or teaching_plan.arc or "Learn lesson",
        "subject": subject,
        "preset_id": preset_id,
        "source": source,
        "source_generation_id": source_generation_id,
        "sections": sections_out,
        "blocks": blocks,
        "media": {},
        "created_at": now,
        "updated_at": now,
        "assembly": {
            "teaching_plan_id": snapshot.teaching_plan_id,
            "teaching_plan_revision": snapshot.teaching_plan_revision,
            "teaching_plan_hash": snapshot.teaching_plan_hash,
            "selection_hash": snapshot.snapshot_hash,
            "ordered_by": "block_ids",
        },
    }


def ordered_block_ids(document: Mapping[str, Any]) -> list[str]:
    """Flatten authoritative block_ids across sections (position then id)."""
    sections = list(document.get("sections") or [])
    sections.sort(key=lambda s: (int(s.get("position") or 0), str(s.get("id") or "")))
    out: list[str] = []
    for section in sections:
        for bid in section.get("block_ids") or []:
            out.append(str(bid))
    return out


def block_component_sequence(document: Mapping[str, Any]) -> list[str]:
    """component_id sequence following authoritative block_ids (for L02 proofs)."""
    blocks = document.get("blocks") if isinstance(document.get("blocks"), dict) else {}
    return [
        str((blocks.get(bid) or {}).get("component_id") or "")
        for bid in ordered_block_ids(document)
    ]

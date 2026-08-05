"""Build an immutable lesson packet from prepare / generation context."""

from __future__ import annotations

from typing import Any, Mapping

from planning.approved_items import ApprovedItemRecord
from planning.whole_lesson.packet import (
    AnchorRecord,
    ApprovedItemRef,
    ImmutableLessonPacket,
    LessonIdentity,
    LessonLimits,
    MisconceptionRecord,
    PriorEstablishedEntry,
    ScopeContract,
    ScopeEntry,
    SlotRecord,
)
from v3_blueprint.skeletons import load_skeleton_catalog

CONCEPTUAL_FIRST_EXPOSURE_SLOTS = ("orient", "explain", "confront", "check")


def _entries(raw: Any, *, prefix: str) -> list[ScopeEntry]:
    entries: list[ScopeEntry] = []
    if not raw:
        return entries
    if isinstance(raw, list):
        for index, item in enumerate(raw):
            if isinstance(item, dict):
                entries.append(
                    ScopeEntry(
                        id=str(item.get("id") or f"{prefix}-{index+1}"),
                        statement=str(item.get("statement") or item.get("text") or item),
                    )
                )
            else:
                entries.append(ScopeEntry(id=f"{prefix}-{index+1}", statement=str(item)))
    return entries


def build_lesson_packet(
    *,
    path_lesson_id: str,
    subject: str,
    grade_level: str,
    objective: str,
    knowledge_type: str,
    lesson_mode: str,
    must_establish: Any,
    must_not_introduce: Any,
    terminology: list[str] | None,
    anchor_id: str,
    anchor_description: str,
    misconceptions: list[Mapping[str, Any]] | None,
    prior_established: list[Any] | None,
    approved_items: tuple[ApprovedItemRecord, ...] | list[ApprovedItemRecord],
    slot_ids: tuple[str, ...] = CONCEPTUAL_FIRST_EXPOSURE_SLOTS,
) -> ImmutableLessonPacket:
    catalog = load_skeleton_catalog()
    slots: list[SlotRecord] = []
    for slot_id in slot_ids:
        raw = dict(catalog.slots.get(slot_id) or {})
        typical_raw = raw.get("typical_intents") or raw.get("candidate_intents") or {}
        if isinstance(typical_raw, Mapping):
            typical = [
                *[str(x) for x in (typical_raw.get("core") or [])],
                *[str(x) for x in (typical_raw.get("optional") or [])],
                *[str(x) for x in (typical_raw.get("typical") or [])],
            ]
        elif isinstance(typical_raw, list):
            typical = [str(x) for x in typical_raw]
        else:
            typical = []
        slots.append(
            SlotRecord(
                slot_id=slot_id,
                purpose=str(raw.get("purpose") or raw.get("intent") or slot_id),
                typical_intents=list(dict.fromkeys(typical)),
                min_blocks=int(raw.get("min_blocks") or 1),
                max_blocks=int(raw.get("max_blocks") or 3),
            )
        )

    misc = [
        MisconceptionRecord(
            id=str(item.get("id") or f"misconception-{index+1}"),
            statement=str(item.get("statement") or item.get("text") or item),
        )
        for index, item in enumerate(misconceptions or [])
        if isinstance(item, Mapping)
    ]

    prior = []
    for index, item in enumerate(prior_established or []):
        if isinstance(item, Mapping):
            prior.append(
                PriorEstablishedEntry(
                    id=str(item.get("id") or f"prior-{index+1}"),
                    statement=str(item.get("statement") or item.get("text") or item),
                )
            )
        else:
            prior.append(PriorEstablishedEntry(id=f"prior-{index+1}", statement=str(item)))

    items = [
        ApprovedItemRef(
            id=record.id,
            card_id=record.card_id,
            stem=record.stem,
            options=[dict(option) for option in record.options],
            correct_key=record.correct_key,
            diagnoses=dict(record.diagnoses),
        )
        for record in approved_items
    ]

    return ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id=path_lesson_id,
            subject=subject,
            grade_level=grade_level,
            objective=objective,
            knowledge_type=knowledge_type,
            lesson_mode=lesson_mode,
        ),
        scope=ScopeContract(
            must_establish=_entries(must_establish, prefix="must"),
            must_not_introduce=_entries(must_not_introduce, prefix="exclude"),
            terminology=list(terminology or []),
        ),
        anchor=AnchorRecord(id=anchor_id, description=anchor_description),
        misconceptions=misc,
        prior_established=prior,
        approved_items=items,
        slots=slots,
        limits=LessonLimits(),
        resource_id="lesson",
    )

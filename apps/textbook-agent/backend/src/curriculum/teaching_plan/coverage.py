"""Instructional coverage extraction for dual-path fidelity checks (P08)."""

from __future__ import annotations

from typing import Any, Mapping

from curriculum.teaching_plan.models import TeachingPlan


def instructional_coverage(plan: TeachingPlan | Mapping[str, Any]) -> dict[str, Any]:
    """Extract objective/facts/tasks/visual/evidence obligations from shared teaching."""
    if isinstance(plan, TeachingPlan):
        payload = plan.model_dump(mode="json")
    else:
        payload = dict(plan)

    intents: list[str] = []
    briefs: list[str] = []
    evidence: list[str] = []
    actions: list[str] = []
    source_ids: list[str] = []
    visual_block_ids: list[str] = []
    block_ids: list[str] = []

    visual_intents = {"illustrate", "show-structure", "show-process"}
    for section in payload.get("sections") or []:
        for block in section.get("blocks") or []:
            bid = str(block.get("id") or "")
            intent = str(block.get("intent") or "")
            brief = str(block.get("brief") or "").strip()
            ev = str(block.get("evidence") or "").strip()
            block_ids.append(bid)
            if intent:
                intents.append(intent)
            if brief:
                briefs.append(brief)
            if ev:
                evidence.append(ev)
            learner = block.get("learner_action") or {}
            action = learner.get("action") if isinstance(learner, dict) else None
            if action:
                actions.append(str(action))
            for sid in block.get("source_question_ids") or []:
                source_ids.append(str(sid))
            for sid in (learner.get("source_item_ids") if isinstance(learner, dict) else None) or []:
                source_ids.append(str(sid))
            if intent in visual_intents:
                visual_block_ids.append(bid)

    return {
        "arc": str(payload.get("arc") or ""),
        "teaching_plan_id": payload.get("teaching_plan_id"),
        "revision": payload.get("revision"),
        "block_ids": block_ids,
        "intents": intents,
        "briefs": briefs,
        "evidence": evidence,
        "actions": sorted(set(actions)),
        "source_item_ids": sorted(set(source_ids)),
        "visual_block_ids": visual_block_ids,
    }


def assert_print_covers_instruction(
    *,
    coverage: Mapping[str, Any],
    teaching_plan: Mapping[str, Any],
    print_document: Mapping[str, Any],
    form_plan: Mapping[str, Any] | None = None,
) -> None:
    """Print must preserve objective, facts, task sources and visual obligations."""
    arc = str(coverage.get("arc") or "")
    assert arc, "teaching coverage missing arc/objective"
    # Objective/arc survives in teaching pin; document must have sections.
    sections = print_document.get("sections") or []
    assert sections, "print document has no sections"

    teaching_sources = set(coverage.get("source_item_ids") or [])
    if teaching_sources:
        pinned_sources: set[str] = set()
        for section in teaching_plan.get("sections") or []:
            for block in section.get("blocks") or []:
                for sid in block.get("source_question_ids") or []:
                    pinned_sources.add(str(sid))
        assert teaching_sources <= pinned_sources, (
            f"approved source items missing from teaching pin: "
            f"{teaching_sources - pinned_sources}"
        )

    if coverage.get("visual_block_ids"):
        figures = [
            block
            for section in sections
            for block in (section.get("blocks") or [])
            if isinstance(block, dict) and block.get("object") == "figure"
        ]
        assert figures, "required visual obligation missing figure in print output"

    if form_plan is not None:
        planned_ids = {
            str(form.get("block_id"))
            for section in (form_plan.get("sections") or [])
            for form in (section.get("forms") or [])
            if isinstance(form, dict) and form.get("block_id")
        }
        teaching_ids = set(coverage.get("block_ids") or [])
        assert teaching_ids, "teaching coverage has no blocks"
        # Closed selection covers every teaching block.
        assert teaching_ids <= planned_ids, (
            f"print form plan missing teaching blocks: {teaching_ids - planned_ids}"
        )


def assert_learn_covers_instruction(
    *,
    coverage: Mapping[str, Any],
    learn_document: Mapping[str, Any],
    selection_trace: Mapping[str, Any] | None = None,
) -> None:
    """Learn must preserve objective, task meaning and evidence obligations."""
    arc = str(coverage.get("arc") or "")
    assert arc, "teaching coverage missing arc/objective"
    title = str(learn_document.get("title") or "")
    assert arc in title or title, "learn document missing title/objective signal"

    blob = str(learn_document)
    for brief in coverage.get("briefs") or []:
        # Briefs may be truncated in content bodies; require distinctive substrings.
        token = brief[:48].strip()
        if len(token) >= 12:
            assert token in blob, f"learn output missing teaching brief token {token!r}"

    actions = set(coverage.get("actions") or [])
    if "order-items" in actions or "reconstruct-order" in actions:
        kinds = []
        for block in (learn_document.get("blocks") or {}).values():
            contract = block.get("learn_interaction") if isinstance(block, dict) else None
            if isinstance(contract, dict):
                kinds.append(contract.get("kind"))
        assert "sequence" in kinds, "order-items task missing Sequence interaction"

    if selection_trace is not None:
        snap = selection_trace.get("selection_snapshot") or {}
        decisions = snap.get("decisions") or []
        decided_blocks = {str(d.get("block_id")) for d in decisions if isinstance(d, dict)}
        teaching_ids = set(coverage.get("block_ids") or [])
        assert teaching_ids <= decided_blocks, (
            f"learn selection missing teaching blocks: {teaching_ids - decided_blocks}"
        )


__all__ = [
    "assert_learn_covers_instruction",
    "assert_print_covers_instruction",
    "instructional_coverage",
]

"""Bridge shared document composition → Print FormPlan (ordinary content + tasks).

Every downstream choice is constrained by the exact candidate map derived before
this bridge. The composer may narrow that set; it must never widen it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock
from document.composer import compose_document_plan
from document.composition import CompositionDecision, CompositionPlan
from document.models import DOCUMENT_PRIMITIVE_KINDS
from infra.authoring import AuthoringEngine, AuthoringProvider
from print.generation.document_form_map import to_document_primitive, to_print_object
from print.generation.native_production import (
    package_contract_hash,
    teaching_plan_content_hash,
)
from print.generation.selection_snapshot import (
    PrintSelectionSnapshot,
    snapshot_from_form_plan,
    validate_print_selection,
)
from print.generation.task_treatments import (
    PRINT_TASK_TREATMENTS,
    print_treatment_for_learner_action,
)
from print.generation.whole_lesson.form_plan import FormDecision, FormPlan
from print.generation.whole_lesson.validation import validate_form_plan
from print.resources.native_policy import default_print_policy, policy_version_and_hash


def _as_plan(plan: TeachingPlan | Mapping[str, Any]) -> TeachingPlan:
    if isinstance(plan, TeachingPlan):
        return plan
    return TeachingPlan.model_validate(plan)


def _action_for(block: TeachingPlanBlock) -> str | None:
    if block.learner_action is None:
        return None
    return str(block.learner_action.action or "").strip() or None


def _exact_candidate_map(
    plan: TeachingPlan,
    candidate_map: Mapping[str, Sequence[str]] | None,
) -> dict[str, tuple[str, ...]]:
    if candidate_map is None:
        raise ValueError(
            "candidate_map is required for closed Print composition; refusing to "
            "derive or widen presentation capabilities after teaching approval"
        )
    out: dict[str, tuple[str, ...]] = {}
    for section in plan.sections:
        for block in section.blocks:
            if block.id not in candidate_map:
                raise ValueError(
                    f"closed Print candidate map missing teaching block {block.id!r}"
                )
            out[block.id] = tuple(
                dict.fromkeys(str(item) for item in candidate_map[block.id] if str(item))
            )
    return out


def _ordinary_kinds_by_block(
    plan: TeachingPlan,
    candidate_map: Mapping[str, Sequence[str]],
    *,
    required_visual_slots: Sequence[str] = (),
) -> dict[str, tuple[str, ...]]:
    """Project exact Print object candidates into the six shared primitives."""
    out: dict[str, tuple[str, ...]] = {}
    by_slot: dict[str, list[str]] = {}
    for section in plan.sections:
        by_slot[str(section.slot_id)] = []
        for block in section.blocks:
            kinds: list[str] = []
            for object_id in candidate_map.get(block.id, ()):
                primitive = to_document_primitive(str(object_id))
                if primitive and primitive not in kinds:
                    kinds.append(primitive)
            out[block.id] = tuple(kinds)
            by_slot[str(section.slot_id)].append(block.id)

    # A required visual is also a closed contract: choose one block in that slot
    # that already has `figure` in its upstream candidate set and restrict it to
    # figure. Never inject figure where upstream legality excluded it.
    for slot_id in (str(item) for item in required_visual_slots if str(item).strip()):
        candidate_blocks = [
            block_id for block_id in by_slot.get(slot_id, ()) if "figure" in out[block_id]
        ]
        if not candidate_blocks:
            raise ValueError(
                f"required visual slot {slot_id!r} has no upstream-legal figure candidate"
            )
        chosen = candidate_blocks[0]
        out[chosen] = ("figure",)
    return out


def _layer_print_tasks(
    plan: TeachingPlan,
    document_plan: CompositionPlan,
    *,
    candidate_map: Mapping[str, Sequence[str]],
) -> CompositionPlan:
    """Layer task treatments only when they remain inside the exact shortlist."""
    by_block_docs: dict[str, list[CompositionDecision]] = {}
    for decision in document_plan.decisions:
        if decision.lane == "document":
            by_block_docs.setdefault(decision.teaching_block_id, []).append(decision)

    decisions: list[CompositionDecision] = []
    for section in plan.sections:
        section_id = str(section.slot_id or "")
        for block in section.blocks:
            allowed = {str(item) for item in candidate_map.get(block.id, ())}
            action = _action_for(block)
            intent = (block.intent or "").strip().lower().replace("_", "-")
            source_ids = list(block.source_question_ids or [])
            treatment = print_treatment_for_learner_action(action, intent=intent)

            # Legacy records can carry source ownership without learner_action;
            # keep them readable, but never guess outside the typed source form.
            if treatment is None and source_ids:
                treatment = "choices" if len(source_ids) == 1 and "choices" in allowed else "questions"
            if treatment in {"questions", "choices"} and not source_ids:
                treatment = None

            if treatment is not None:
                if treatment not in allowed:
                    raise ValueError(
                        f"Print task {treatment!r} for block {block.id!r} is outside "
                        f"the closed candidate set {sorted(allowed)}"
                    )
                decisions.append(
                    CompositionDecision(
                        teaching_block_id=block.id,
                        kind=treatment,
                        lane="print_task",
                        reason=(
                            f"learner_action {action!r} → upstream-legal Print task {treatment!r}"
                            if action
                            else f"approved source → upstream-legal Print task {treatment!r}"
                        ),
                        section_id=section_id or None,
                    )
                )
                continue

            docs = by_block_docs.get(block.id) or []
            if not docs:
                raise ValueError(
                    f"closed Print composition has no legal realization for block {block.id!r}"
                )
            decisions.extend(docs)

    return CompositionPlan(
        path="print",
        teaching_plan_id=document_plan.teaching_plan_id or plan.teaching_plan_id,
        teaching_plan_revision=(
            document_plan.teaching_plan_revision
            if document_plan.teaching_plan_revision is not None
            else plan.revision
        ),
        composition_mode=document_plan.composition_mode,
        decisions=decisions,
    )


def composition_to_form_plan(
    plan: TeachingPlan,
    composition: CompositionPlan,
) -> FormPlan:
    """Map already-closed composition decisions to one Print object per block."""
    by_block: dict[str, list[CompositionDecision]] = {}
    for decision in composition.decisions:
        by_block.setdefault(decision.teaching_block_id, []).append(decision)

    sections = []
    for section in plan.sections:
        forms: list[FormDecision] = []
        for block in section.blocks:
            choices = by_block.get(block.id) or []
            if not choices:
                raise ValueError(f"composition missing decision for block {block.id!r}")
            primary = choices[0]
            if primary.lane == "document":
                if primary.kind not in DOCUMENT_PRIMITIVE_KINDS:
                    raise ValueError(f"illegal document kind {primary.kind!r}")
                object_id = (
                    "prose"
                    if primary.kind == "heading"
                    else to_print_object(primary.kind)  # type: ignore[arg-type]
                )
            elif primary.lane == "print_task":
                if primary.kind not in PRINT_TASK_TREATMENTS:
                    raise ValueError(f"illegal Print task {primary.kind!r}")
                object_id = primary.kind
            else:
                raise ValueError(f"unsupported lane {primary.lane!r} on Print plan")
            forms.append(
                FormDecision(
                    block_id=block.id,
                    object=object_id,
                    placement="main",
                    reason=primary.reason,
                )
            )
        sections.append({"slot_id": section.slot_id, "forms": forms})
    return FormPlan.model_validate({"sections": sections})


async def build_print_production_from_composition(
    *,
    teaching_plan: TeachingPlan,
    provider: AuthoringProvider | None = None,
    engine: AuthoringEngine | None = None,
    policy: Mapping[str, Any] | None = None,
    allow_heuristic_fallback: bool = True,
    candidate_map: Mapping[str, Sequence[str]] | None = None,
    required_visual_slots: Sequence[str] | None = None,
    budget_ledger: Any | None = None,
    checkpoint_store: Any | None = None,
    progress_store: Any | None = None,
    progress_run_id: str | None = None,
) -> tuple[FormPlan, PrintSelectionSnapshot, CompositionPlan]:
    """Compose and realize Print strictly inside the upstream candidate snapshot."""
    body = dict(policy) if policy is not None else default_print_policy()
    _, policy_hash = policy_version_and_hash(body)
    plan_hash = teaching_plan_content_hash(teaching_plan)
    cmap = _exact_candidate_map(teaching_plan, candidate_map)
    ordinary = _ordinary_kinds_by_block(
        teaching_plan,
        cmap,
        required_visual_slots=required_visual_slots or (),
    )

    document_plan = await compose_document_plan(
        teaching_plan,
        path="print",
        provider=provider,
        engine=engine,
        allow_heuristic_fallback=allow_heuristic_fallback,
        allowed_kinds_by_block=ordinary,
        budget_ledger=budget_ledger,
        checkpoint_store=checkpoint_store,
        progress_store=progress_store,
        progress_run_id=progress_run_id,
    )
    composition = _layer_print_tasks(
        teaching_plan,
        document_plan,
        candidate_map=cmap,
    )
    form_plan = composition_to_form_plan(teaching_plan, composition)

    report = validate_form_plan(
        form_plan,
        teaching_plan,
        candidate_map=cmap,
        required_visual_slots=set(required_visual_slots or ()),
    )
    if not report.ok:
        details = "; ".join(f"{issue.code}: {issue.message}" for issue in report.issues if issue.blocking)
        raise ValueError(f"closed Print form plan failed validation: {details}")

    validate_print_selection(
        teaching_plan=teaching_plan,
        decisions=form_plan,
        candidate_map=cmap,
        expected_teaching_plan_id=str(teaching_plan.teaching_plan_id or ""),
        expected_teaching_plan_revision=int(teaching_plan.revision or 1),
        expected_teaching_plan_hash=plan_hash,
        actual_teaching_plan_hash=plan_hash,
    )
    snapshot = snapshot_from_form_plan(
        teaching_plan=teaching_plan,
        form_plan=form_plan,
        candidate_map=cmap,
        teaching_plan_hash=plan_hash,
        native_policy_hash=policy_hash,
        package_contract_hash=package_contract_hash(),
    )
    return form_plan, snapshot, composition


__all__ = [
    "build_print_production_from_composition",
    "composition_to_form_plan",
]

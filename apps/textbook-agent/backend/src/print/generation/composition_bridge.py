"""Bridge shared document composition → Print FormPlan (ordinary content + tasks).

Ordinary forms are chosen by ``document.composer`` (LLM) then mapped to Print
catalogue object ids. Learner-response blocks use Print-only task treatments.
FormPlan remains a Print layout carrier — it is no longer the ordinary-content
selector (closed catalogue LLM selection).
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock
from document.composer import compose_document_plan
from document.composition import CompositionDecision, CompositionPlan
from document.models import DOCUMENT_PRIMITIVE_KINDS
from infra.authoring import AuthoringEngine, AuthoringProvider
from print.generation.document_form_map import (
    PRIMITIVE_TO_PRINT_OBJECT,
    to_print_object,
)
from print.generation.selection_snapshot import (
    PrintSelectionDecision,
    PrintSelectionSnapshot,
    snapshot_from_form_plan,
)
from print.generation.task_treatments import (
    PRINT_TASK_TREATMENTS,
    print_treatment_for_learner_action,
)
from print.generation.whole_lesson.form_plan import FormDecision, FormPlan
from print.generation.work_orders import compile_print_work_orders
from print.resources.native_policy import (
    default_print_policy,
    policy_version_and_hash,
)
from print.generation.native_production import (
    package_contract_hash,
    teaching_plan_content_hash,
)


def _as_plan(plan: TeachingPlan | Mapping[str, Any]) -> TeachingPlan:
    if isinstance(plan, TeachingPlan):
        return plan
    return TeachingPlan.model_validate(plan)


def _action_for(block: TeachingPlanBlock) -> str | None:
    if block.learner_action is None:
        return None
    return str(block.learner_action.action or "").strip() or None


def _layer_print_tasks(
    plan: TeachingPlan,
    document_plan: CompositionPlan,
) -> CompositionPlan:
    """Replace/override ordinary nodes for blocks that need Print task treatments.

    One decision per teaching block for FormPlan compatibility: if the block
    requires a response surface, emit print_task; otherwise keep first document
    choice for that block (extra document nodes from multi-node composition are
    preserved as additional forms when they share the same block — FormPlan
    historically is 1:1, so we emit the primary document node + task separately
    only when task replaces content for that block).
    """
    by_block_docs: dict[str, list[CompositionDecision]] = {}
    for decision in document_plan.decisions:
        if decision.lane != "document":
            continue
        by_block_docs.setdefault(decision.teaching_block_id, []).append(decision)

    decisions: list[CompositionDecision] = []
    for section in plan.sections:
        section_id = str(section.slot_id or "")
        for block in section.blocks:
            action = _action_for(block)
            intent = (block.intent or "").strip().lower().replace("_", "-")
            treatment = print_treatment_for_learner_action(action, intent=intent)
            # Assessment ownership: source_question_ids may only ride on
            # questions/choices PlannedBlocks. Prefer an assessment treatment
            # when the teaching block owns item IDs even without an action.
            source_ids = list(getattr(block, "source_question_ids", None) or [])
            if treatment is None and source_ids:
                treatment = "choices" if len(source_ids) == 1 else "questions"
            if treatment is not None:
                decisions.append(
                    CompositionDecision(
                        teaching_block_id=block.id,
                        kind=treatment,
                        lane="print_task",
                        reason=(
                            f"learner_action {action!r} → Print task {treatment!r}"
                            if action
                            else f"source_question_ids → Print task {treatment!r}"
                        ),
                        section_id=section_id or None,
                    )
                )
                continue
            docs = by_block_docs.get(block.id) or []
            if docs:
                decisions.extend(docs)
            else:
                # Composer omitted this block — fall through empty; caller validates.
                pass
    return CompositionPlan(
        path="print",
        teaching_plan_id=document_plan.teaching_plan_id or plan.teaching_plan_id,
        teaching_plan_revision=(
            document_plan.teaching_plan_revision
            if document_plan.teaching_plan_revision is not None
            else plan.revision
        ),
        decisions=decisions,
    )


def composition_to_form_plan(
    plan: TeachingPlan,
    composition: CompositionPlan,
) -> FormPlan:
    """Map composition decisions to Print FormPlan objects (no raw page-object LLM pick)."""
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
            # FormPlan is 1 object per block — use the primary (first) decision.
            primary = choices[0]
            if primary.lane == "document":
                if primary.kind not in DOCUMENT_PRIMITIVE_KINDS:
                    raise ValueError(f"illegal document kind {primary.kind!r}")
                # PlannedBlock forbids standalone `heading` objects — section
                # titles own headings. Collapse to prose for Print assembly.
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
) -> tuple[FormPlan, PrintSelectionSnapshot, CompositionPlan]:
    """Compose ordinary structure, layer Print tasks, emit FormPlan + snapshot."""
    body = dict(policy) if policy is not None else default_print_policy()
    _, policy_hash = policy_version_and_hash(body)
    plan_hash = teaching_plan_content_hash(teaching_plan)

    document_plan = await compose_document_plan(
        teaching_plan,
        path="print",
        provider=provider,
        engine=engine,
        allow_heuristic_fallback=allow_heuristic_fallback,
    )
    composition = _layer_print_tasks(teaching_plan, document_plan)
    form_plan = composition_to_form_plan(teaching_plan, composition)

    # Composition owns ordinary selection. Merge chosen objects (and the full
    # ordinary Print vocabulary) into the candidate map so FormPlan validation
    # does not reject composer choices that were outside the closed catalogue
    # shortlist for a block.
    ordinary_objects = tuple(sorted(PRIMITIVE_TO_PRINT_OBJECT.values()))
    task_objects = tuple(sorted(PRINT_TASK_TREATMENTS))
    cmap: dict[str, tuple[str, ...]] = {}
    if candidate_map:
        cmap = {str(k): tuple(str(x) for x in v) for k, v in candidate_map.items()}
    for section in form_plan.sections:
        for decision in section.forms:
            prior = list(cmap.get(decision.block_id, ()))
            merged = list(
                dict.fromkeys(
                    [*prior, decision.object, *ordinary_objects, *task_objects]
                )
            )
            cmap[decision.block_id] = tuple(merged)

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

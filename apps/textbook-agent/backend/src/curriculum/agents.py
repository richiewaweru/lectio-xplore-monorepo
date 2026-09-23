from __future__ import annotations

import json
import uuid
from typing import Any, TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent

from curriculum.lesson_sourcebook.models import (
    LessonSourcebook,
    LessonSourcebookDraft,
    SourcebookEntry,
)
from curriculum.llm_contract_errors import structured_output_errors as _schema_errors
from curriculum.models import (
    CanonicalPathPlan,
    ComponentSelection,
    ConstructorOutput,
    PathPlanDraft,
    PathPlannerRequest,
    PathStructuralPagePlan,
    PathStructuralPlan,
)
from curriculum.planner_diagnostics import log_planner_attempt_failed
from curriculum.prompts import (
    capability_selector_prompt,
    component_selector_prompt,
    constructor_prompt,
    lesson_sourcebook_writer_prompt,
    path_planner_prompt,
    path_structural_planner_prompt,
    plan_editor_prompt,
    shared_task_writer_prompt,
)
from curriculum.shared_tasks.models import SharedTaskDraft, SharedTaskSpec
from curriculum.shared_tasks.service import teaching_plan_hash
from curriculum.teaching_plan.compatibility import response_bearing_action
from curriculum.teaching_plan.models import TeachingPlan
from curriculum.validation import (
    PathPlanningError,
    PathValidationError,
    normalize_constructor_fields,
    normalize_path_plan_draft,
    validate_canonical_path_plan,
)
from infra.authoring.capability_selector import CapabilitySelection
from infra.config import settings
from infra.llm.runner import RetryPolicy, run_llm
from infra.authoring.model_policy import (
    NATIVE_CAPABILITY_SELECTOR,
    V2_COMPONENT_SELECTOR,
    V2_PATH_CHAT_EDITOR,
    V2_PATH_PLANNER,
    V2_PATH_STRUCTURAL_PLANNER,
    V3_CONSTRUCTOR,
    V3_LESSON_SOURCEBOOK_WRITER,
    V3_SHARED_TASK_WRITER,
    get_v3_model_settings,
    get_v3_slot,
)
from infra.authoring.structured_provider import (
    NO_OUTPUT_RETRY,
    prepare_structured_agent,
)

OutputT = TypeVar("OutputT", bound=BaseModel)


class _SharedTaskDraftEnvelope(BaseModel):
    tasks: list[SharedTaskDraft]


async def run_lesson_sourcebook_writer(
    plan: TeachingPlan,
    *,
    trace_id: str | None = None,
) -> LessonSourcebook:
    """Author canonical content commitments with code-owned entry identities."""
    draft = await _run_structured(
        node=V3_LESSON_SOURCEBOOK_WRITER,
        caller="v3_lesson_sourcebook_writer",
        output_type=LessonSourcebookDraft,
        system_prompt=lesson_sourcebook_writer_prompt(),
        user_payload={
            "teaching_plan": plan.model_dump(mode="json"),
            "sourcebook_needs": [
                {"block_id": block.id, "needs": list(block.sourcebook_needs)}
                for section in plan.sections
                for block in section.blocks
                if block.sourcebook_needs
            ],
        },
        trace_id=trace_id,
    )
    return LessonSourcebook(
        teaching_plan_id=str(plan.teaching_plan_id or "teaching-plan"),
        teaching_plan_revision=int(plan.revision or 1),
        teaching_plan_hash=teaching_plan_hash(plan),
        entries=[
            SourcebookEntry(
                id=f"source-{index + 1}",
                type=entry.type,
                purpose=entry.purpose,
                content=entry.content,
                provenance_refs=list(entry.provenance_refs),
            )
            for index, entry in enumerate(draft.entries)
        ],
    )


async def run_shared_task_writer(
    plan: TeachingPlan,
    *,
    sourcebook: LessonSourcebook | None = None,
    approved_items: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> list[SharedTaskSpec]:
    """Author task meaning once; code binds each draft to its block/revision."""
    response_blocks = [
        block
        for section in plan.sections
        for block in section.blocks
        if block.learner_action is not None
        and response_bearing_action(block.learner_action.action)
    ]
    draft = await _run_structured(
        node=V3_SHARED_TASK_WRITER,
        caller="v3_shared_task_writer",
        output_type=_SharedTaskDraftEnvelope,
        system_prompt=shared_task_writer_prompt(),
        user_payload={
            "teaching_plan": plan.model_dump(mode="json"),
            "response_blocks": [block.id for block in response_blocks],
            "sourcebook": sourcebook.model_dump(mode="json") if sourcebook else None,
            "approved_items": approved_items or {},
        },
        trace_id=trace_id,
    )
    if len(draft.tasks) != len(response_blocks):
        raise ValueError("shared task writer must return exactly one task per response-bearing block")
    source_index = sourcebook.by_id() if sourcebook else {}
    approved_items = approved_items or {}
    tasks: list[SharedTaskSpec] = []
    for index, (block, task) in enumerate(zip(response_blocks, draft.tasks, strict=True)):
        source_ids = list(block.source_question_ids)
        if block.task_mode == "assessment" and not source_ids:
            raise ValueError(f"assessment block {block.id!r} has no approved source")
        refs = [ref for ref in block.sourcebook_refs if ref in source_index]
        tasks.append(
            SharedTaskSpec(
                id=f"task-{block.id}",
                teaching_plan_id=str(plan.teaching_plan_id or "teaching-plan"),
                teaching_plan_revision=int(plan.revision or 1),
                teaching_plan_hash=teaching_plan_hash(plan),
                teaching_block_id=block.id,
                mode="assessment" if block.task_mode == "assessment" else "formative",
                action=block.learner_action.action,  # type: ignore[union-attr]
                purpose=block.learner_action.purpose,  # type: ignore[union-attr]
                prompt=task.prompt,
                difficulty=task.difficulty,
                sourcebook_refs=refs,
                expected_evidence=task.expected_evidence,
                response=task.response,
                evaluation=task.evaluation,
                feedback=task.feedback,
                approved_source_ids=source_ids,
            )
        )
    return tasks


async def _run_structured(
    *,
    node: str,
    caller: str,
    output_type: type[OutputT],
    system_prompt: str,
    user_payload: dict[str, Any],
    trace_id: str | None,
) -> OutputT:
    model, provider_output, structured_context, spec, _source = prepare_structured_agent(
        node_name=node,
        output_type=output_type,
    )
    slot = get_v3_slot(node)
    agent = Agent(
        model=model,
        output_type=provider_output,
        system_prompt=system_prompt,
        # Repair is owned by the caller's outer attempt loop (see
        # run_path_structural_planner). pydantic-ai's in-library output retry
        # appends to the same message history, which replays the model's own
        # invalid response — fatal on DeepSeek when that response is
        # reasoning-only with empty content.
        retries=NO_OUTPUT_RETRY,
    )
    result = await run_llm(
        trace_id=trace_id or str(uuid.uuid4()),
        caller=caller,
        generation_id=None,
        agent=agent,
        user_prompt=json.dumps(user_payload, indent=2, sort_keys=True),
        model=model,
        slot=slot,
        spec=spec,
        node=node,
        model_settings=get_v3_model_settings(node),
        retry_policy=RetryPolicy(
            max_attempts=1,
            call_timeout_seconds=float(settings.v3_timeout_stage1_seconds),
        ),
        structured_context=structured_context,
    )
    raw = result.output
    if isinstance(raw, output_type):
        return raw
    if hasattr(raw, "model_dump"):
        return output_type.model_validate(raw.model_dump())
    return output_type.model_validate(raw)


async def run_path_planner(
    request: PathPlannerRequest,
    *,
    trace_id: str | None = None,
) -> CanonicalPathPlan:
    """Plan a unit path with at most one targeted repair attempt."""
    tid = trace_id or str(uuid.uuid4())
    base_payload = request.model_dump(mode="json")
    errors: list[str] = []
    previous_output: dict[str, Any] | None = None

    for attempt in (1, 2):
        payload: dict[str, Any] = dict(base_payload)
        if attempt == 2:
            payload = {
                **base_payload,
                "repair": {
                    "instruction": (
                        "Your previous output violated the path contract. Return "
                        "the complete corrected JSON matching the minimal plan "
                        "shape. Change only what the listed errors name."
                    ),
                    "previous_output": previous_output,
                    "validation_errors": errors,
                },
            }
        try:
            draft = await _run_structured(
                node=V2_PATH_PLANNER,
                caller="v2_path_planner",
                output_type=PathPlanDraft,
                system_prompt=path_planner_prompt(),
                user_payload=payload,
                trace_id=f"{tid}:plan{attempt}",
            )
        except Exception as exc:
            errors = _schema_errors(exc)
            previous_output = None
            log_planner_attempt_failed(
                node=V2_PATH_PLANNER,
                attempt=attempt,
                errors=errors,
                exc=exc,
                repair_attached=attempt == 2,
                will_retry=attempt == 1,
            )
            if attempt == 2:
                raise PathPlanningError(errors) from exc
            continue

        try:
            plan = normalize_path_plan_draft(draft)
            errors = validate_canonical_path_plan(plan)
            if not errors:
                return plan
        except PathValidationError as exc:
            errors = [str(exc)]
            plan = None  # type: ignore[assignment]

        previous_output = draft.model_dump(mode="json", exclude_none=True)
        log_planner_attempt_failed(
            node=V2_PATH_PLANNER,
            attempt=attempt,
            errors=errors,
            repair_attached=attempt == 2,
            will_retry=attempt == 1,
        )
        if attempt == 2:
            raise PathPlanningError(errors)

    raise PathPlanningError(errors or ["path planner produced no usable result"])


async def run_component_selector(
    context: dict[str, Any],
    *,
    trace_id: str | None = None,
) -> ComponentSelection:
    return await _run_structured(
        node=V2_COMPONENT_SELECTOR,
        caller="v2_component_selector",
        output_type=ComponentSelection,
        system_prompt=component_selector_prompt(),
        user_payload=context,
        trace_id=trace_id,
    )


async def run_capability_selector(
    context: dict[str, Any],
    *,
    trace_id: str | None = None,
) -> CapabilitySelection:
    return await _run_structured(
        node=NATIVE_CAPABILITY_SELECTOR,
        caller="native_capability_selector",
        output_type=CapabilitySelection,
        system_prompt=capability_selector_prompt(),
        user_payload=context,
        trace_id=trace_id,
    )


async def run_interaction_selection(
    context: dict[str, Any],
    *,
    trace_id: str | None = None,
) -> CapabilitySelection:
    """Pick among legal Learn interaction candidates using interaction-selection.md."""
    from curriculum.prompts import interaction_selection_prompt

    return await _run_structured(
        node=NATIVE_CAPABILITY_SELECTOR,
        caller="interaction_selection",
        output_type=CapabilitySelection,
        system_prompt=interaction_selection_prompt(),
        user_payload=context,
        trace_id=trace_id,
    )


async def run_path_structural_planner(
    fixed_context: dict[str, Any],
    *,
    trace_id: str | None = None,
) -> PathStructuralPlan | PathStructuralPagePlan:
    """Plan lesson structure, with one targeted repair attempt.

    The typed output schema is the primary protection. This loop is the net
    beneath it: at most two fresh attempts, the second one carrying the previous
    output and the exact violations. Each attempt builds a new Agent, so no
    provider message history is ever replayed.
    """
    from curriculum.prompts import path_structural_planner_page_prompt
    from curriculum.structural_validation import (
        PathStructuralContextError,
        validate_path_structural_result,
    )

    use_page = bool(fixed_context.get("native_whole_lesson"))
    output_type = PathStructuralPagePlan if use_page else PathStructuralPlan
    system_prompt = (
        path_structural_planner_page_prompt()
        if use_page
        else path_structural_planner_prompt()
    )
    expected_slots = [
        str(slot.get("slot_id")) if isinstance(slot, dict) else str(slot)
        for slot in (fixed_context.get("recommended_slots") or fixed_context.get("slots") or [])
        if (isinstance(slot, dict) and slot.get("slot_id")) or (not isinstance(slot, dict) and str(slot).strip())
    ]
    legal_slots = {
        str(slot.get("slot_id")): dict(slot)
        for slot in (fixed_context.get("legal_slots") or [])
        if isinstance(slot, dict) and slot.get("slot_id")
    }
    expected_visual_required = {
        str(slot["slot_id"]): bool(slot.get("visual_required"))
        for slot in (fixed_context.get("slots") or [])
        if isinstance(slot, dict) and slot.get("slot_id")
    }
    tid = trace_id or str(uuid.uuid4())
    errors: list[str] = []
    previous_output: dict[str, Any] | None = None

    for attempt in (1, 2):
        payload = fixed_context
        if attempt == 2:
            if use_page:
                repair_instruction = (
                    "Your previous output violated the fixed contract. Return "
                    "the complete corrected JSON. Change only what the listed "
                    "errors name. Return one semantic section payload for each "
                    "supplied slot, in the supplied order. Do not add or remove "
                    "sections. Do not output objective, concept/card identity, "
                    "slot identity, card_id, or visual_required; code owns those fields."
                )
            else:
                repair_instruction = (
                    "Your previous output violated the fixed contract. Return "
                    "the complete corrected JSON. Change only what the listed "
                    "errors name. Section ids and roles must match selected_slots: "
                    "do not invent slot roles, and preserve the objective and concept id exactly."
                    " Echo each supplied slot's visual_required flag exactly; "
                    "do not clear an authoritative true flag."
                )
            payload = {
                **fixed_context,
                "repair": {
                    "instruction": repair_instruction,
                    "previous_output": previous_output,
                    "validation_errors": errors,
                },
            }
        try:
            plan = await _run_structured(
                node=V2_PATH_STRUCTURAL_PLANNER,
                caller="v2_path_structural_planner",
                output_type=output_type,
                system_prompt=system_prompt,
                user_payload=payload,
                trace_id=f"{tid}:structural{attempt}",
            )
        except Exception as exc:
            errors = _schema_errors(exc)
            # Raw model text never escapes _run_structured, so there is no
            # previous output to echo on this branch. The pydantic messages are
            # actionable on their own.
            previous_output = None
            log_planner_attempt_failed(
                node=V2_PATH_STRUCTURAL_PLANNER,
                attempt=attempt,
                errors=errors,
                exc=exc,
                repair_attached=attempt == 2,
                will_retry=attempt == 1,
            )
            if attempt == 2:
                raise
            continue

        errors = validate_path_structural_result(
            plan,
            expected_slots=expected_slots,
            expected_visual_required=expected_visual_required,
            legal_slots=legal_slots or None,
            max_slots=int(fixed_context.get("max_slots") or len(expected_slots)),
        )
        if not errors:
            return plan
        previous_output = plan.model_dump(mode="json", exclude_none=True)
        log_planner_attempt_failed(
            node=V2_PATH_STRUCTURAL_PLANNER,
            attempt=attempt,
            errors=errors,
            repair_attached=attempt == 2,
            will_retry=attempt == 1,
        )
        if attempt == 2:
            raise PathStructuralContextError(errors)

    raise PathStructuralContextError(
        errors or ["structural planner produced no usable result"]
    )


async def run_constructor(
    subject: str,
    grade_level: str,
    raw_text: str,
    *,
    correction: str | None = None,
    clarifying_answer: str | None = None,
    trace_id: str | None = None,
) -> ConstructorOutput:
    payload: dict[str, Any] = {
        "subject": subject,
        "grade_level": grade_level,
        "raw_text": raw_text,
    }
    if correction is not None:
        payload["correction"] = correction
    if clarifying_answer is not None:
        payload["clarifying_answer"] = clarifying_answer
    result = await _run_structured(
        node=V3_CONSTRUCTOR,
        caller="v3_constructor",
        output_type=ConstructorOutput,
        system_prompt=constructor_prompt(),
        user_payload=payload,
        trace_id=trace_id,
    )
    objective, starting = normalize_constructor_fields(
        destination_objective=result.destination_objective,
        starting_knowledge=result.starting_knowledge,
    )
    return result.model_copy(
        update={
            "destination_objective": objective,
            "starting_knowledge": starting,
        }
    )


async def run_plan_chat_edit(
    plan: CanonicalPathPlan,
    message: str,
    *,
    unit_context: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> CanonicalPathPlan:
    """Edit a path via chat with at most one targeted repair attempt."""
    tid = trace_id or str(uuid.uuid4())
    base_payload: dict[str, Any] = {
        "current_plan": plan.model_dump(mode="json"),
        "edit_request": message,
        "unit_context": unit_context or {},
    }
    errors: list[str] = []
    previous_output: dict[str, Any] | None = None

    for attempt in (1, 2):
        payload = dict(base_payload)
        if attempt == 2:
            payload = {
                **base_payload,
                "repair": {
                    "instruction": (
                        "Your previous output violated the path contract. Return "
                        "the complete corrected minimal plan JSON. Change only "
                        "what the listed errors name."
                    ),
                    "previous_output": previous_output,
                    "validation_errors": errors,
                },
            }
        try:
            draft = await _run_structured(
                node=V2_PATH_CHAT_EDITOR,
                caller="v2_path_chat_editor",
                output_type=PathPlanDraft,
                system_prompt=plan_editor_prompt(),
                user_payload=payload,
                trace_id=f"{tid}:edit{attempt}",
            )
        except Exception as exc:
            errors = _schema_errors(exc)
            previous_output = None
            log_planner_attempt_failed(
                node=V2_PATH_CHAT_EDITOR,
                attempt=attempt,
                errors=errors,
                exc=exc,
                repair_attached=attempt == 2,
                will_retry=attempt == 1,
            )
            if attempt == 2:
                raise PathPlanningError(errors) from exc
            continue

        try:
            edited = normalize_path_plan_draft(draft)
            errors = validate_canonical_path_plan(edited)
            if not errors:
                return edited
        except PathValidationError as exc:
            errors = [str(exc)]

        previous_output = draft.model_dump(mode="json", exclude_none=True)
        log_planner_attempt_failed(
            node=V2_PATH_CHAT_EDITOR,
            attempt=attempt,
            errors=errors,
            repair_attached=attempt == 2,
            will_retry=attempt == 1,
        )
        if attempt == 2:
            raise PathPlanningError(errors)

    raise PathPlanningError(errors or ["path chat editor produced no usable result"])

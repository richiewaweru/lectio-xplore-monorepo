from __future__ import annotations

import json
import uuid
from typing import Any, TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent

from core.config import settings
from core.llm.runner import RetryPolicy, run_llm
from planning.llm_contract_errors import structured_output_errors as _schema_errors
from planning.models import (
    CanonicalPathPlan,
    ComponentSelection,
    ConstructorOutput,
    PathPlanDraft,
    PathPlannerRequest,
    PathStructuralPlan,
)
from planning.prompts import (
    component_selector_prompt,
    constructor_prompt,
    path_planner_prompt,
    path_structural_planner_prompt,
    plan_editor_prompt,
)
from planning.planner_diagnostics import log_planner_attempt_failed
from planning.validation import (
    PathPlanningError,
    PathValidationError,
    normalize_constructor_fields,
    normalize_path_plan_draft,
    validate_canonical_path_plan,
)
from v3_execution.config import get_v3_model, get_v3_model_settings, get_v3_slot, get_v3_spec
from v3_execution.config.models import (
    V2_COMPONENT_SELECTOR,
    V2_PATH_CHAT_EDITOR,
    V2_PATH_PLANNER,
    V2_PATH_STRUCTURAL_PLANNER,
    V3_CONSTRUCTOR,
)
from v3_execution.llm_helpers import NO_OUTPUT_RETRY, structured_output_type_for_model


OutputT = TypeVar("OutputT", bound=BaseModel)


async def _run_structured(
    *,
    node: str,
    caller: str,
    output_type: type[OutputT],
    system_prompt: str,
    user_payload: dict[str, Any],
    trace_id: str | None,
) -> OutputT:
    model = get_v3_model(node)
    spec = get_v3_spec(node)
    slot = get_v3_slot(node)
    agent = Agent(
        model=model,
        output_type=structured_output_type_for_model(output_type, spec=spec),
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
        except Exception as exc:  # noqa: BLE001 - classified below
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


async def run_path_structural_planner(
    fixed_context: dict[str, Any],
    *,
    trace_id: str | None = None,
) -> PathStructuralPlan:
    """Plan lesson structure, with one targeted repair attempt.

    The typed output schema is the primary protection. This loop is the net
    beneath it: at most two fresh attempts, the second one carrying the previous
    output and the exact violations. Each attempt builds a new Agent, so no
    provider message history is ever replayed.
    """
    from planning.prompts import path_structural_planner_page_prompt
    from planning.structural_validation import (
        PathStructuralContextError,
        validate_path_structural_result,
    )

    use_page = bool(fixed_context.get("native_whole_lesson"))
    system_prompt = (
        path_structural_planner_page_prompt()
        if use_page
        else path_structural_planner_prompt()
    )
    expected_slots = [
        slot["slot_id"]
        for slot in (fixed_context.get("slots") or [])
        if isinstance(slot, dict) and slot.get("slot_id")
    ]
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
            payload = {
                **fixed_context,
                "repair": {
                    "instruction": (
                        "Your previous output violated the fixed contract. Return "
                        "the complete corrected JSON. Change only what the listed "
                        "errors name. Section ids and roles are fixed: do not "
                        "rename, add, remove, or reorder them, and preserve the "
                        "objective and concept id exactly."
                        " Echo each supplied slot's visual_required flag exactly; "
                        "do not clear an authoritative true flag."
                    ),
                    "previous_output": previous_output,
                    "validation_errors": errors,
                },
            }
        try:
            plan = await _run_structured(
                node=V2_PATH_STRUCTURAL_PLANNER,
                caller="v2_path_structural_planner",
                output_type=PathStructuralPlan,
                system_prompt=system_prompt,
                user_payload=payload,
                trace_id=f"{tid}:structural{attempt}",
            )
        except Exception as exc:  # noqa: BLE001 - classified below, re-raised on attempt 2
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
        except Exception as exc:  # noqa: BLE001 - classified below
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

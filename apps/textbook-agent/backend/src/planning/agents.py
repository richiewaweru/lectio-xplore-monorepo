from __future__ import annotations

import json
import uuid
import asyncio
from typing import Any, TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent

from core.config import settings
from core.llm.runner import RetryPolicy, run_llm
from planning.models import (
    ComponentSelection,
    ConstructorOutput,
    MergeCriticResult,
    PathPlan,
    PathPlannerRequest,
    PathStructuralPlan,
    PlannedLesson,
)
from planning.prompts import (
    component_selector_prompt,
    constructor_prompt,
    merge_critic_prompt,
    path_planner_prompt,
    path_structural_planner_prompt,
    plan_editor_prompt,
)
from planning.validation import normalize_declared_external_prerequisites, validate_path_plan
from v3_execution.config import get_v3_model, get_v3_model_settings, get_v3_slot, get_v3_spec
from v3_execution.config.models import (
    V2_COMPONENT_SELECTOR,
    V2_MERGE_CRITIC,
    V2_PATH_CHAT_EDITOR,
    V2_PATH_PLANNER,
    V2_PATH_STRUCTURAL_PLANNER,
    V3_CONSTRUCTOR,
)
from v3_execution.llm_helpers import structured_output_type_for_model


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
) -> PathPlan:
    plan = await _run_structured(
        node=V2_PATH_PLANNER,
        caller="v2_path_planner",
        output_type=PathPlan,
        system_prompt=path_planner_prompt(),
        user_payload={
            **request.model_dump(mode="json"),
            "planner_output_contract": {
                "prerequisites": "slugs of earlier lessons in this path only",
                "external_prerequisites": (
                    "assumed capabilities; each must match starting_knowledge or "
                    "scope_contract.assumed_prerequisites"
                ),
            },
        },
        trace_id=trace_id,
    )
    plan = normalize_declared_external_prerequisites(plan)
    validate_path_plan(plan)
    return plan


async def run_merge_critic(
    lesson_a: PlannedLesson,
    lesson_b: PlannedLesson,
    *,
    trace_id: str | None = None,
) -> MergeCriticResult:
    return await _run_structured(
        node=V2_MERGE_CRITIC,
        caller="v2_merge_critic",
        output_type=MergeCriticResult,
        system_prompt=merge_critic_prompt(),
        user_payload={
            "lesson_a": lesson_a.model_dump(mode="json"),
            "lesson_b": lesson_b.model_dump(mode="json"),
        },
        trace_id=trace_id,
    )


async def run_adjacent_merge_critics(
    plan: PathPlan,
    *,
    trace_id: str | None = None,
) -> list[dict[str, object]]:
    lessons = plan.lessons
    by_slug = {lesson.concept_candidate.slug: lesson for lesson in lessons}
    pair_keys: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _add_pair(lesson_a: PlannedLesson, lesson_b: PlannedLesson) -> None:
        key = (lesson_a.concept_candidate.slug, lesson_b.concept_candidate.slug)
        if key in seen:
            return
        seen.add(key)
        pair_keys.append(key)

    for nomination in plan.adjacent_merge_reviews:
        lesson_a = by_slug.get(nomination.lesson_a)
        lesson_b = by_slug.get(nomination.lesson_b)
        if lesson_a is None or lesson_b is None:
            continue
        _add_pair(lesson_a, lesson_b)

    for index, lesson in enumerate(lessons):
        if not lesson.merge_warning:
            continue
        if index + 1 < len(lessons):
            _add_pair(lesson, lessons[index + 1])
        if index > 0:
            _add_pair(lessons[index - 1], lesson)

    pairs = [(by_slug[a], by_slug[b]) for a, b in pair_keys]
    if not pairs:
        return []

    results = await asyncio.gather(
        *[
            run_merge_critic(
                lesson_a,
                lesson_b,
                trace_id=f"{trace_id or 'path'}:merge:{index}",
            )
            for index, (lesson_a, lesson_b) in enumerate(pairs)
        ]
    )
    return [
        {
            "lesson_a": lesson_a.concept_candidate.slug,
            "lesson_b": lesson_b.concept_candidate.slug,
            **result.model_dump(mode="json"),
        }
        for (lesson_a, lesson_b), result in zip(pairs, results, strict=True)
    ]


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
    from planning.prompts import path_structural_planner_page_prompt

    use_page = bool(fixed_context.get("native_whole_lesson"))
    return await _run_structured(
        node=V2_PATH_STRUCTURAL_PLANNER,
        caller="v2_path_structural_planner",
        output_type=PathStructuralPlan,
        system_prompt=(
            path_structural_planner_page_prompt()
            if use_page
            else path_structural_planner_prompt()
        ),
        user_payload=fixed_context,
        trace_id=trace_id,
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
    return await _run_structured(
        node=V3_CONSTRUCTOR,
        caller="v3_constructor",
        output_type=ConstructorOutput,
        system_prompt=constructor_prompt(),
        user_payload=payload,
        trace_id=trace_id,
    )


async def run_plan_chat_edit(
    plan: PathPlan,
    message: str,
    *,
    unit_context: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> PathPlan:
    return await _run_structured(
        node=V2_PATH_CHAT_EDITOR,
        caller="v2_path_chat_editor",
        output_type=PathPlan,
        system_prompt=plan_editor_prompt(),
        user_payload={
            "current_plan": plan.model_dump(mode="json"),
            "edit_request": message,
            "unit_context": unit_context or {},
        },
        trace_id=trace_id,
    )

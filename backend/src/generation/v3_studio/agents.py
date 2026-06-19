from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic_ai import Agent

from core.llm.runner import run_llm
from core.llm.runner import RetryPolicy
from v3_blueprint.compiler import BlueprintCompiler
from v3_blueprint.models import ProductionBlueprint
from v3_execution.config import (
    get_v3_model,
    get_v3_slot,
    get_v3_spec,
    lesson_architect_model_settings,
)
from v3_execution.config.timeouts import V3_TIMEOUTS

from generation.v3_studio.dtos import (
    ProductionBlueprintEnvelope,
    V3InputForm,
    V3SignalSummary,
)
from generation.v3_studio.prompts import (
    ADJUST_SYSTEM,
    SIGNAL_SYSTEM,
    build_parent_context_for_supplement,
    build_supplement_architect_system_prompt,
    build_supplement_user_prompt,
)

_CALLER = "v3_studio"
EmitFn = Callable[[str, dict[str, Any]], Awaitable[None]]

SUPPLEMENT_DEFAULT_DEPTH = {
    "exit_ticket": "quick",
    "quiz": "standard",
    "worksheet": "standard",
}


async def extract_signals(form: V3InputForm, *, trace_id: str | None = None) -> V3SignalSummary:
    node = "v3_signal_extractor"
    tid = trace_id or str(uuid.uuid4())
    model = get_v3_model(node)
    spec = get_v3_spec(node)
    slot = get_v3_slot(node)
    agent = Agent(
        model=model,
        output_type=V3SignalSummary,
        system_prompt=SIGNAL_SYSTEM,
    )
    user = (
        f"Grade level: {form.grade_level}\n"
        f"Subject: {form.subject}\n"
        f"Duration minutes: {form.duration_minutes}\n"
        f"Topic: {form.topic}\n"
        f"Subtopics: {', '.join(form.subtopics) if form.subtopics else '(none)'}\n"
        f"Prior knowledge: {form.prior_knowledge or '(none)'}\n"
        f"Lesson mode: {form.lesson_mode}\n"
        f"Lesson mode other: {form.lesson_mode_other or '(none)'}\n"
        f"Intended outcome: {form.intended_outcome}\n"
        f"Intended outcome other: {form.intended_outcome_other or '(none)'}\n"
        f"Learner level: {form.learner_level}\n"
        f"Reading level: {form.reading_level}\n"
        f"Language support: {form.language_support}\n"
        f"Prior knowledge level: {form.prior_knowledge_level}\n"
        f"Support needs: {', '.join(form.support_needs) if form.support_needs else '(none)'}\n"
        f"Learning preferences: {', '.join(form.learning_preferences) if form.learning_preferences else '(none)'}\n\n"
        f"Additional notes (optional):\n{form.free_text.strip() or '(none)'}"
    )
    result = await run_llm(
        trace_id=tid,
        caller=_CALLER,
        generation_id=None,
        agent=agent,
        user_prompt=user,
        model=model,
        slot=slot,
        spec=spec,
        section_id=None,
        node=node,
        retry_policy=RetryPolicy(call_timeout_seconds=float(V3_TIMEOUTS["signal_extractor"])),
    )
    raw = result.output
    if isinstance(raw, V3SignalSummary):
        return raw
    raise RuntimeError("signal extractor returned unexpected output")


def _validate_blueprint(bp: ProductionBlueprint) -> None:
    """
    Validate the architect-produced blueprint and raise structured errors.
    """
    from pydantic import ValidationError

    try:
        compiler_result = BlueprintCompiler().compile_all(bp)
    except ValidationError as exc:
        field_errors = [f"  {'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        raise RuntimeError(
            f"Blueprint structure invalid ({len(field_errors)} error(s)):\n"
            + "\n".join(field_errors)
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"Blueprint compiler raised unexpected error: {exc}") from exc

    if isinstance(compiler_result, list) and compiler_result:
        formatted = "\n".join(f"  - {e}" for e in compiler_result)
        raise RuntimeError(
            f"Blueprint failed domain validation:\n{formatted}\n"
            "Check component slugs, section_field uniqueness, and question_plan."
        )


def _render_resource_spec(
    inferred_resource_type: str | None,
    duration_minutes: int,
) -> str:
    """
    Render the resource spec for the inferred resource type into a prompt-ready string.

    Falls back to 'lesson' if the resource type is unknown or has no spec.
    Infers depth from duration: under 20 min → quick, over 45 min → deep, else standard.
    active_roles and active_supports are left empty — the architect decides those.
    """
    from resource_specs.loader import get_spec, list_spec_ids
    from resource_specs.renderer import render_spec_for_prompt

    resource_type = (inferred_resource_type or "lesson").lower().strip().replace(" ", "_")

    available = list_spec_ids()
    if resource_type not in available:
        resource_type = "lesson"

    depth = "quick" if duration_minutes < 20 else "deep" if duration_minutes > 45 else "standard"

    try:
        spec = get_spec(resource_type)
        return render_spec_for_prompt(
            spec,
            depth=depth,
            active_roles=[],
            active_supports=[],
        )
    except Exception:
        return (
            f"Resource type: {resource_type}\n"
            "(No detailed spec available for this type — use judgment based on resource intent.)"
        )


def _build_chunked_resource_spec(
    inferred_resource_type: str | None,
    duration_minutes: int,
) -> dict[str, Any]:
    from resource_specs.loader import get_spec, list_spec_ids
    from resource_specs.renderer import render_spec_for_prompt

    resource_type = (inferred_resource_type or "lesson").lower().strip().replace(" ", "_")
    if resource_type not in list_spec_ids():
        resource_type = "lesson"
    depth = "quick" if duration_minutes < 20 else "deep" if duration_minutes > 45 else "standard"

    try:
        spec = get_spec(resource_type)
        rendered = render_spec_for_prompt(
            spec,
            depth=depth,
            active_roles=[],
            active_supports=[],
        )
        return {
            "resource_type": resource_type,
            "depth": depth,
            "spec": spec.model_dump(mode="json"),
            "rendered": rendered,
        }
    except Exception:
        return {
            "resource_type": resource_type,
            "depth": depth,
            "spec": {},
            "rendered": (
                f"Resource type: {resource_type}\n"
                "(No detailed spec available for this type — use judgment based on resource intent.)"
            ),
        }


async def generate_production_blueprint(
    *,
    signals: V3SignalSummary,
    form: V3InputForm,
    generation_id: str | None = None,
    emit_event: EmitFn | None = None,
    trace_id: str | None = None,
) -> ProductionBlueprint:
    from v3_blueprint.planning.assembler import assemble_blueprint
    from v3_blueprint.planning.retry import run_stage1_with_retry, run_stage2

    chunked_resource_spec = _build_chunked_resource_spec(
        inferred_resource_type=signals.inferred_resource_type,
        duration_minutes=form.duration_minutes,
    )
    plan = await run_stage1_with_retry(
        signals=signals,
        form=form,
        resource_spec=chunked_resource_spec,
        emit_event=emit_event,
        generation_id=generation_id,
        trace_id=trace_id,
    )
    briefs = await run_stage2(
        plan=plan,
        signals=signals,
        form=form,
        resource_spec=chunked_resource_spec,
        emit_event=emit_event,
        generation_id=generation_id,
        trace_id=trace_id,
    )
    bp = assemble_blueprint(
        plan,
        briefs,
        subject=form.subject.strip() or "General",
        title=form.topic.strip() or "Generated Lesson",
        resource_type=(signals.inferred_resource_type or "lesson").strip().lower(),
    )
    _validate_blueprint(bp)
    return bp


async def adjust_production_blueprint(
    blueprint: ProductionBlueprint,
    adjustment: str,
    *,
    trace_id: str | None = None,
) -> ProductionBlueprint:
    node = "v3_blueprint_adjust"
    tid = trace_id or str(uuid.uuid4())
    model = get_v3_model(node)
    spec = get_v3_spec(node)
    slot = get_v3_slot(node)
    agent = Agent(
        model=model,
        output_type=ProductionBlueprintEnvelope,
        system_prompt=ADJUST_SYSTEM,
    )
    user = (
        "Current blueprint JSON:\n"
        f"{blueprint.model_dump_json(indent=2)}\n\n"
        f"Teacher adjustment:\n{adjustment.strip()}"
    )
    result = await run_llm(
        trace_id=tid,
        caller=_CALLER,
        generation_id=None,
        agent=agent,
        user_prompt=user,
        model=model,
        slot=slot,
        spec=spec,
        section_id=None,
        node=node,
    )
    raw = result.output
    envelope = raw if isinstance(raw, ProductionBlueprintEnvelope) else None
    if envelope is None and hasattr(raw, "blueprint"):
        envelope = ProductionBlueprintEnvelope(blueprint=raw.blueprint)  # type: ignore[arg-type]
    if envelope is None:
        raise RuntimeError("blueprint adjust returned unexpected output")
    bp = envelope.blueprint
    _validate_blueprint(bp)
    return bp


def _render_target_resource_spec(target_resource_type: str) -> str:
    from resource_specs.loader import get_spec, list_spec_ids
    from resource_specs.renderer import render_spec_for_prompt

    resource_type = target_resource_type.lower().strip().replace(" ", "_")
    available = list_spec_ids()
    if resource_type not in available:
        raise ValueError(f"No resource spec for type: {resource_type}")

    depth = SUPPLEMENT_DEFAULT_DEPTH.get(resource_type, "standard")
    spec = get_spec(resource_type)
    return render_spec_for_prompt(
        spec,
        depth=depth,
        active_roles=[],
        active_supports=[],
    )


def _parent_section_ids(parent_artifact: dict[str, Any]) -> set[str]:
    blueprint = parent_artifact.get("blueprint")
    if not isinstance(blueprint, dict):
        return set()
    sections = blueprint.get("sections")
    if not isinstance(sections, list):
        return set()
    ids: set[str] = set()
    for section in sections:
        if isinstance(section, dict):
            sid = section.get("section_id")
            if isinstance(sid, str) and sid:
                ids.add(sid)
    return ids


def _assert_child_section_ids_distinct(
    parent_artifact: dict[str, Any],
    child_bp: ProductionBlueprint,
) -> None:
    parent_ids = _parent_section_ids(parent_artifact)
    child_ids = {section.section_id for section in child_bp.sections}
    overlap = parent_ids & child_ids
    if overlap:
        raise RuntimeError(
            f"Supplement blueprint reused parent section IDs: {', '.join(sorted(overlap))}"
        )


async def generate_supplement_blueprint(
    *,
    parent_artifact: dict[str, Any],
    target_resource_type: str,
    trace_id: str | None = None,
) -> ProductionBlueprint:
    node = "v3_lesson_architect"
    tid = trace_id or str(uuid.uuid4())
    model = get_v3_model(node)
    spec = get_v3_spec(node)
    slot = get_v3_slot(node)
    agent = Agent(
        model=model,
        output_type=ProductionBlueprintEnvelope,
        system_prompt=build_supplement_architect_system_prompt(),
    )
    resource_spec_block = _render_target_resource_spec(target_resource_type)
    parent_context = build_parent_context_for_supplement(parent_artifact)
    user = build_supplement_user_prompt(
        target_resource_type=target_resource_type,
        resource_spec_block=resource_spec_block,
        parent_context_json=json.dumps(parent_context, indent=2),
    )
    result = await run_llm(
        trace_id=tid,
        caller=_CALLER,
        generation_id=None,
        agent=agent,
        user_prompt=user,
        model=model,
        slot=slot,
        spec=spec,
        section_id=None,
        node=node,
        model_settings=lesson_architect_model_settings(),
        retry_policy=RetryPolicy(call_timeout_seconds=float(V3_TIMEOUTS["lesson_architect"])),
    )
    raw = result.output
    envelope = raw if isinstance(raw, ProductionBlueprintEnvelope) else None
    if envelope is None and hasattr(raw, "blueprint"):
        envelope = ProductionBlueprintEnvelope(blueprint=raw.blueprint)  # type: ignore[arg-type]
    if envelope is None:
        raise RuntimeError("supplement architect returned unexpected output")
    bp = envelope.blueprint
    derived = parent_artifact.get("derived")
    if isinstance(derived, dict):
        subject = derived.get("subject")
        if isinstance(subject, str) and subject.strip():
            bp.metadata.subject = subject.strip()
    _validate_blueprint(bp)
    _assert_child_section_ids_distinct(parent_artifact, bp)
    return bp


__all__ = [
    "SUPPLEMENT_DEFAULT_DEPTH",
    "adjust_production_blueprint",
    "extract_signals",
    "generate_production_blueprint",
    "generate_supplement_blueprint",
]

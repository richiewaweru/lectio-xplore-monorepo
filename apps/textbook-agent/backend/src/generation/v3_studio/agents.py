from __future__ import annotations

import uuid

from pydantic_ai import Agent

from core.llm.runner import RetryPolicy, run_llm
from generation.v3_studio.dtos import ProductionBlueprintEnvelope, V3InputForm, V3SignalSummary
from generation.v3_studio.prompts import ADJUST_SYSTEM, SIGNAL_SYSTEM
from v3_blueprint.compiler import BlueprintCompiler
from v3_blueprint.models import ProductionBlueprint
from v3_execution.config import get_v3_model, get_v3_model_settings, get_v3_slot, get_v3_spec
from v3_execution.config.timeouts import V3_TIMEOUTS
from v3_execution.llm_helpers import NO_OUTPUT_RETRY, prepare_structured_agent

_CALLER = "v3_studio"


def _validate_blueprint(bp: ProductionBlueprint) -> None:
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


async def extract_signals(form: V3InputForm, *, trace_id: str | None = None) -> V3SignalSummary:
    node = "v3_signal_extractor"
    tid = trace_id or str(uuid.uuid4())
    model, provider_output, structured_context, spec, _source = prepare_structured_agent(
        node_name=node,
        output_type=V3SignalSummary,
    )
    slot = get_v3_slot(node)
    agent = Agent(
        model=model,
        output_type=provider_output,
        system_prompt=SIGNAL_SYSTEM,
        retries=NO_OUTPUT_RETRY,
    )
    user = (
        f"Grade level: {form.grade_level}\n"
        f"Subject: {form.subject}\n"
        f"Duration minutes: {form.duration_minutes}\n"
        f"Resource type: {form.resource_type}\n"
        f"Topic: {form.topic}\n"
        f"Subtopics: {', '.join(form.subtopics) if form.subtopics else '(none)'}\n"
        f"Prior knowledge: {form.prior_knowledge or '(none)'}\n"
        f"Outcome: {form.outcome}\n"
        f"Struggle: {form.struggle or '(none)'}\n"
        f"Learner level: {form.learner_level}\n"
        f"Reading level: {form.reading_level}\n"
        f"Language support: {form.language_support}\n"
        f"Prior knowledge level: {form.prior_knowledge_level}\n"
        "\n"
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
        model_settings=get_v3_model_settings(node),
        retry_policy=RetryPolicy(call_timeout_seconds=float(V3_TIMEOUTS["signal_extractor"])),
        structured_context=structured_context,
    )
    raw = result.output
    if isinstance(raw, V3SignalSummary):
        return raw
    raise RuntimeError("signal extractor returned unexpected output")


async def adjust_production_blueprint(
    blueprint: ProductionBlueprint,
    adjustment: str,
    *,
    trace_id: str | None = None,
) -> ProductionBlueprint:
    node = "v3_blueprint_adjust"
    tid = trace_id or str(uuid.uuid4())
    model, provider_output, structured_context, spec, _source = prepare_structured_agent(
        node_name=node,
        output_type=ProductionBlueprintEnvelope,
    )
    slot = get_v3_slot(node)
    agent = Agent(
        model=model,
        output_type=provider_output,
        system_prompt=ADJUST_SYSTEM,
        retries=NO_OUTPUT_RETRY,
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
        model_settings=get_v3_model_settings(node),
        structured_context=structured_context,
    )
    raw = result.output
    envelope = raw if isinstance(raw, ProductionBlueprintEnvelope) else None
    if envelope is None and hasattr(raw, "blueprint"):
        envelope = ProductionBlueprintEnvelope(blueprint=raw.blueprint)  # type: ignore[arg-type]
    if envelope is None:
        raise RuntimeError("blueprint adjust returned unexpected output")
    return envelope.blueprint


__all__ = ["_validate_blueprint", "adjust_production_blueprint", "extract_signals"]

from __future__ import annotations

import json
import uuid

from pydantic_ai import Agent

from core.config import settings
from core.llm.runner import RetryPolicy, run_llm
from core.prompts import effective_prompt_text
from generation.v3_studio.dtos import V3InputForm, V3SignalSummary
from generation.v3_studio.prompts import _planner_index_block, build_v3_shared_prefix
from v3_blueprint.planning.models import StructuralPlan
from v3_blueprint.planning.validators import validate_structural_plan_roles
from v3_execution.config import get_v3_model, get_v3_model_settings, get_v3_slot, get_v3_spec
from v3_execution.llm_helpers import NO_OUTPUT_RETRY, prepare_structured_agent

_CALLER = "v3_chunked_architect"
STAGE1_NODE = "v3_stage1_planner"

_PLANNER_INDEX_MARKER = "@@PLANNER_INDEX_BLOCK@@"


def _load_stage1_static_body() -> str:
    return effective_prompt_text("structural-planner")


def build_stage1_system_prompt(*, path_prepared: bool = False) -> str:
    shared_prefix = build_v3_shared_prefix()
    planner_block = _planner_index_block()

    static_body = _load_stage1_static_body().replace(_PLANNER_INDEX_MARKER, planner_block)
    prompt = f"{shared_prefix}{static_body}"
    if not path_prepared:
        return prompt

    return prompt.replace(
        """  Give each card 2-4 misconceptions that are specific beliefs a learner would
  confidently act on, not slips, carelessness, or general confusion. If there
  is genuinely no known misconception, emit an empty list and set
  no_known_misconceptions=true. Never pad a list.""",
        """  Give each card ZERO to THREE misconceptions. Apply this test to every
  candidate: could a learner holding this belief confidently choose a corresponding wrong answer?
  If not, it is a knowledge gap, not a
  misconception. If there is genuinely no known misconception, emit an empty
  list and set no_known_misconceptions=true. Never pad a list.""",
    ).replace(
        """- A card has 2-4 real misconceptions, or explicitly sets
  no_known_misconceptions=true with an empty list.""",
        """- A card has 0-3 real misconceptions, or explicitly sets
  no_known_misconceptions=true with an empty list.""",
    )


def build_stage1_user_message(
    *,
    signals: V3SignalSummary,
    form: V3InputForm,
    resource_spec: dict,
    skeleton_catalog: dict | None = None,
    previous_errors: list[str] | None = None,
) -> str:
    payload = (
        f"Signals JSON:\n{signals.model_dump_json(indent=2)}\n\n"
        f"Form JSON:\n{form.model_dump_json(indent=2)}\n\n"
        f"RESOURCE SPEC JSON:\n{json.dumps(resource_spec, indent=2, sort_keys=True)}"
    )
    slots = skeleton_catalog.get("slots") if isinstance(skeleton_catalog, dict) else None
    if isinstance(slots, dict) and slots:
        payload += "\n\nSKELETON SLOT IDS (the only valid section roles):\n" + ", ".join(
            sorted(str(slot_id) for slot_id in slots)
        )
    if previous_errors:
        payload += (
            "\n\nVALIDATION ERRORS FROM PREVIOUS ATTEMPT "
            "(fix all of these):\n"
            + "\n".join(f"- {error}" for error in previous_errors)
        )
    return payload


def _validate_stage1_roles(
    plan: StructuralPlan,
    skeleton_catalog: dict | None,
) -> None:
    errors = validate_structural_plan_roles(plan, skeleton_catalog)
    if errors:
        raise ValueError(errors[0])


async def _call_stage1(
    signals: V3SignalSummary,
    form: V3InputForm,
    resource_spec: dict,
    *,
    trace_id: str | None = None,
    generation_id: str | None = None,
    previous_errors: list[str] | None = None,
    skeleton_catalog: dict | None = None,
    path_prepared: bool = False,
) -> StructuralPlan:
    import traceback
    try:
        node = STAGE1_NODE
        tid = trace_id or generation_id or str(uuid.uuid4())
        model, provider_output, structured_context, spec, _source = prepare_structured_agent(
            node_name=node,
            output_type=StructuralPlan,
        )
        slot = get_v3_slot(node)
        agent = Agent(
            model=model,
            output_type=provider_output,
            system_prompt=build_stage1_system_prompt(path_prepared=path_prepared),
            retries=NO_OUTPUT_RETRY,
        )
        result = await run_llm(
            trace_id=tid,
            caller=_CALLER,
            generation_id=generation_id,
            agent=agent,
            user_prompt=build_stage1_user_message(
                signals=signals,
                form=form,
                resource_spec=resource_spec,
                skeleton_catalog=skeleton_catalog,
                previous_errors=previous_errors,
            ),
            model=model,
            slot=slot,
            spec=spec,
            section_id=None,
            node=node,
            model_settings=get_v3_model_settings(node),
            retry_policy=RetryPolicy(
                max_attempts=1,
                call_timeout_seconds=float(settings.v3_timeout_stage1_seconds),
            ),
            structured_context=structured_context,
        )
        raw = result.output
        if isinstance(raw, StructuralPlan):
            plan = raw
        elif hasattr(raw, "model_dump"):
            plan = StructuralPlan.model_validate(raw.model_dump())
        else:
            plan = StructuralPlan.model_validate(raw)
        _validate_stage1_roles(plan, skeleton_catalog)
        return plan
    except Exception as exc:
        tb = traceback.format_exc()
        print(
            f"\n[_CALL_STAGE1 ERROR]"
            f" generation_id={generation_id}"
            f" type={type(exc).__name__}"
            f"\nmessage={str(exc)}"
            f"\ntraceback:\n{tb}",
            flush=True,
        )
        raise


__all__ = [
    "STAGE1_NODE",
    "_call_stage1",
    "build_stage1_system_prompt",
    "build_stage1_user_message",
]

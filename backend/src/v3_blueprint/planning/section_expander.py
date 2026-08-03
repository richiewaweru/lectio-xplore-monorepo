from __future__ import annotations

import json
import uuid

from pydantic_ai import Agent
from pydantic_ai.messages import CachePoint

from contracts.lectio import get_component_card
from core.config import settings
from core.llm.runner import RetryPolicy, run_llm
from core.llm.types import ModelFamily
from core.prompts import effective_prompt_text
from generation.v3_studio.dtos import V3InputForm, V3SignalSummary
from generation.v3_studio.prompts import build_v3_shared_prefix
from generation.v3_studio.signal_map import summarise_form_supports
from v3_blueprint.planning.models import SectionBrief, SectionPlan, StructuralPlan
from v3_execution.config import get_v3_model, get_v3_model_settings, get_v3_slot, get_v3_spec
from v3_execution.llm_helpers import structured_output_type_for_model

_CALLER = "v3_chunked_architect"
STAGE2_NODE = "v3_stage2_expander"


def build_stage2_system_prompt() -> str:
    shared_prefix = build_v3_shared_prefix()
    return shared_prefix + effective_prompt_text("section-expander")


def build_stage2_user_message(
    plan: StructuralPlan,
    current_section: SectionPlan,
    prior_briefs: list[SectionBrief],
    component_cards: dict[str, dict],
    form: V3InputForm,
) -> str:

    # Format prior briefs — full content, not summarised (serial mode only).
    # Parallel mode always passes prior_briefs=[] and uses plan-derived continuity.
    prior_block = ""
    if prior_briefs:
        prior_block = (
            "PRIOR SECTION BRIEFS\n"
            "(what earlier sections have committed to — "
            "build on these, do not repeat them)\n"
        )
        for brief in prior_briefs:
            if getattr(brief, "_failed", False):
                prior_block += (
                    f"\n  Section '{brief.section_id}': GENERATION FAILED\n"
                    f"  Do not reference or build on this section.\n"
                    f"  Use the structural plan and anchor for continuity.\n"
                )
            else:
                prior_block += f"\n  Section '{brief.section_id}':\n"
                for comp in brief.components:
                    prior_block += (
                        f"    {comp.component_id}:\n"
                        f"      {comp.content_intent}\n"
                    )
    else:
        continuity_lines = [
            "PLAN CONTINUITY (from the structural plan — no prior briefs)",
            f"  Anchor example: {plan.anchor.example}",
            f"  Anchor reuse:   {plan.anchor.reuse_scope}",
            "  Section transitions:",
        ]
        for s in plan.sections:
            note = s.transition_note or "first section — no prior"
            marker = "→" if s.id == current_section.id else " "
            continuity_lines.append(f"  {marker} [{s.id}] {note}")
        prior_block = "\n".join(continuity_lines) + "\n"

    # Format full section sequence — so Stage 2 knows where this section sits
    sequence_lines = []
    for s in plan.sections:
        marker = "→" if s.id == current_section.id else " "
        sequence_lines.append(
            f"  {marker} [{s.role.upper()}] {s.id}: {s.title}"
        )
    sequence_block = "\n".join(sequence_lines)

    # Format approved card misconceptions relevant to this section.
    pitfall_block = ""
    section_slugs = {c.slug for c in current_section.components}
    current_card = next(
        (card for card in plan.cards if card.id == current_section.card_id),
        None,
    )
    if current_card is not None and "pitfall-alert" in section_slugs:
        pitfall_block = "KNOWN PITFALLS TO ADDRESS IN THIS SECTION:\n"
        for misconception in current_card.misconceptions:
            pitfall_block += (
                f"  {misconception.id}: {misconception.description}\n"
            )

    return f"""LESSON PLAN
———————————————————————————————————————————————
Goal:               {plan.lesson_intent.goal}
Structure rationale:{plan.lesson_intent.structure_rationale}
Lesson mode:        {plan.lesson_mode}
Anchor:             {plan.anchor.example}
Anchor reuse:       {plan.anchor.reuse_scope}
Variant:            {plan.variant_spec().label}
Learner group:      {plan.variant_spec().group_description}
Voice:              {plan.variant_spec().voice.register_name}, {plan.variant_spec().voice.tone}
Prior knowledge:    {", ".join(plan.prior_knowledge)}
Signal supports:    {", ".join(summarise_form_supports(form)) or "none"}

FULL SECTION SEQUENCE (your section is marked →):
{sequence_block}

{pitfall_block}
———————————————————————————————————————————————
{prior_block}
———————————————————————————————————————————————
YOUR SECTION:
  id:              {current_section.id}
  title:           {current_section.title}
  role:            {current_section.role}
  visual_required: {current_section.visual_required}
  transition_note: {current_section.transition_note or "first section — no prior"}

  Components to brief (in this order):
{chr(10).join(f"    {c.slug}: {c.purpose}" for c in current_section.components)}

COMPONENT CARDS — capacity limits for your section's components:
{json.dumps(component_cards, indent=2)}

Write the SectionBrief JSON for section '{current_section.id}' only.
"""


def _load_component_cards_for_section(section: SectionPlan) -> dict[str, dict]:
    cards: dict[str, dict] = {}
    for component in section.components:
        card = get_component_card(component.slug)
        if card is not None:
            cards[component.slug] = card
    return cards


def _prefix_user_content(
    *,
    signals: V3SignalSummary,
    form: V3InputForm,
    resource_spec: dict,
    plan: StructuralPlan,
    family: ModelFamily,
) -> list[str | CachePoint]:
    blocks: list[str | CachePoint] = [
        signals.model_dump_json(),
        form.model_dump_json(),
        json.dumps(resource_spec, sort_keys=True),
        plan.model_dump_json(),
    ]
    if family == ModelFamily.ANTHROPIC:
        blocks.append(CachePoint())
    return blocks


async def _call_stage2_section(
    *,
    plan: StructuralPlan,
    section: SectionPlan,
    prior_briefs: list[SectionBrief],
    component_cards: dict[str, dict],
    signals: V3SignalSummary,
    form: V3InputForm,
    resource_spec: dict,
    generation_id: str | None = None,
    trace_id: str | None = None,
    previous_errors: list[str] | None = None,
) -> SectionBrief:
    import time
    import traceback

    node = STAGE2_NODE
    tid = trace_id or generation_id or str(uuid.uuid4())
    model = get_v3_model(node)
    spec = get_v3_spec(node)
    slot = get_v3_slot(node)
    agent = Agent(
        model=model,
        output_type=structured_output_type_for_model(SectionBrief, spec=spec),
        system_prompt=build_stage2_system_prompt(),
    )
    section_message = build_stage2_user_message(
        plan=plan,
        current_section=section,
        prior_briefs=prior_briefs,
        component_cards=component_cards,
        form=form,
    )
    if previous_errors:
        section_message += (
            "\n\nVALIDATION ERRORS FROM PREVIOUS ATTEMPT "
            "(fix all of these):\n"
            + "\n".join(f"- {error}" for error in previous_errors)
        )

    user_prompt = [
        *_prefix_user_content(
            signals=signals,
            form=form,
            resource_spec=resource_spec,
            plan=plan,
            family=spec.family,
        ),
        section_message,
    ]

    print(
        f"\n[_CALL_STAGE2] generation_id={generation_id}"
        f" section_id={section.id}"
        f" model={STAGE2_NODE}"
        f" timeout={settings.v3_timeout_stage2_section_seconds}s",
        flush=True,
    )
    t0 = time.perf_counter()
    try:
        result = await run_llm(
            trace_id=tid,
            caller=_CALLER,
            generation_id=generation_id,
            agent=agent,
            user_prompt=user_prompt,  # type: ignore[arg-type]
            model=model,
            slot=slot,
            spec=spec,
            section_id=section.id,
            node=node,
            model_settings=get_v3_model_settings(node),
            retry_policy=RetryPolicy(
                max_attempts=1,
                call_timeout_seconds=float(settings.v3_timeout_stage2_section_seconds),
            ),
        )
    except Exception as exc:
        elapsed = round(time.perf_counter() - t0, 1)
        print(
            f"\n[_CALL_STAGE2 ERROR] generation_id={generation_id}"
            f" section_id={section.id}"
            f" elapsed={elapsed}s"
            f" type={type(exc).__name__}"
            f"\nmessage={str(exc)}"
            f"\n{traceback.format_exc()}",
            flush=True,
        )
        raise

    elapsed = round(time.perf_counter() - t0, 1)
    print(
        f"\n[_CALL_STAGE2 DONE] generation_id={generation_id}"
        f" section_id={section.id}"
        f" elapsed={elapsed}s",
        flush=True,
    )
    raw = result.output
    if isinstance(raw, SectionBrief):
        return raw
    if hasattr(raw, "model_dump"):
        return SectionBrief.model_validate(raw.model_dump())
    return SectionBrief.model_validate(raw)


__all__ = [
    "STAGE2_NODE",
    "_call_stage2_section",
    "_load_component_cards_for_section",
    "build_stage2_system_prompt",
    "build_stage2_user_message",
]

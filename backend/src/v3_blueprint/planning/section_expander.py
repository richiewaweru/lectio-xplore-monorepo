from __future__ import annotations

import json
import uuid

from pydantic_ai import Agent
from pydantic_ai.messages import CachePoint

from contracts.lectio import get_component_card
from core.config import settings
from core.llm.runner import RetryPolicy, run_llm
from core.llm.types import ModelFamily
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
    return shared_prefix + """You are a lesson elaborator.

A lesson architect has already planned this lesson completely.
You have been given the full structural plan and everything
the architect decided.

Your only job is to write a precise content brief for each
component in the section you are given.

You are not re-planning. You are not making structural decisions.
You are translating the architect's intent into specific,
actionable instructions that a writer can execute without
asking any questions.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT A GOOD CONTENT_INTENT LOOKS LIKE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A content_intent is a writer brief. It tells the writer:
  - What this component must do for the learner at this exact point
  - How the anchor example should appear (if it appears here)
  - What the prior section established that this one builds on
  - What this component must not do (repeat, introduce too early)
  - What cognitive move the learner makes reading this component

Bad:  "explain equivalent fractions using an example"
Good: "use the pizza anchor to show that 2/4 and 1/2 describe the
       same area; name numerator and denominator explicitly for the
       first time; do not introduce symbolic comparison yet —
       that is the worked example's job"

Bad:  "practice questions on fractions"
Good: "two warm questions asking students to identify which pizza
       diagram matches a given fraction; use anchor slice counts
       from the model section; no symbolic notation yet"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANCHOR RULE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The anchor example is named in the plan you have been given.
Use it by that exact name whenever this component touches the concept.
Do not substitute, vary, generalise, or rename it.
The anchor is a commitment the architect made — honour it.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTINUITY RULE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You may have been given the brief from the lesson's opening (anchor) section.
Read them before writing. Your briefs must:
  - Build on what prior sections established
  - Not repeat concepts or examples already covered
  - Prime what the next section needs without doing its job

The transition_note on your section tells you exactly what
the prior section established and what your section does with it.
That note is your entry point into this section.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VOICE RULE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The voice register is in the plan. Write your content_intent
instructions in a tone that reflects it.
  simple   → short sentences, no jargon, concrete first
  balanced → grade-appropriate vocabulary, moderate density
  formal   → precise terminology, full explanation expected

The writer inherits your register from your content_intent.
If you write a brief that implies complex prose in a simple
register lesson, the writer will produce the wrong output.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPONENT CAPACITY RULE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Each component card in your context includes capacity limits.
Your content_intent must stay within what the component can render.
Do not brief a writer to produce five worked examples if the
component holds two. Do not brief paragraph-length prose for a
component with a 40-word capacity.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT YOU CANNOT DO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  - Remove a planned component
  - Replace a planned component's slug or position
  - Introduce a concept the plan did not allocate to this section

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Return valid JSON containing all required documented fields.
Prefer the documented schema and keys. Additional detail must not replace,
rename, or omit required fields.

Keep content_intent concise where possible. Preserve every instruction required
by the downstream writer. Do not omit meaningful pedagogical information solely
to satisfy a length preference.

Every planned component must receive a brief. Do not replace planned component
IDs with invented IDs.

{
  "section_id": "must match the section you were given",

  "components": [
    {
      "component_id": "slug from the section plan — unchanged",
      "content_intent": "your writer brief — specific, actionable, and complete"
    }
  ],

  "visual_strategy": null
}

If visual_required is true for this section, replace null with:
{
  "subject": "what the visual depicts — one sentence",
  "visual_job": "what the visual is FOR - e.g. introduce anchor visually, summarize section explanation as labeled diagram, support question q-practice-2 with an unlabeled figure",
  "type_hint": "diagram | chart | illustration | comparison",
  "anchor_link": "how this visual connects to the anchor example",
  "visual_style": "diagram_precision | illustration",
  "must_show": ["2 to 5 short required elements or labels"],
  "must_not_show": ["2 to 5 short exclusions that would distract or mislead"],
  "source_question_ids": ["question IDs this visual supports - empty list if none"],
  "frames": [
    {
      "description": "what frame 1 shows",
      "must_show": ["..."]
    },
    {
      "description": "what frame 2 shows",
      "must_show": ["..."]
    }
  ]
}

HARD RULES:
- visual_strategy must be populated if visual_required is true
- visual_job describes PURPOSE, not runtime timing
- visual_style is required when visual_strategy is populated: use diagram_precision
  for diagrams/charts/comparisons or any label-heavy image; use illustration
  only for ordinary explanatory artwork
- must_show items are visual elements or short labels, never caption sentences;
  captions belong in the component caption field
- must_show items are positive statements of what appears; any absence constraint
  ("no X", "without X", "never X", "avoid X") belongs in must_not_show
- Prefer 2 to 5 short, concrete items in must_show and must_not_show
- If the section's visual-capable component is diagram-series, frames must have at least 2 entries
- If the visual supports a specific question, add its ID to source_question_ids
- component_id values must exactly match slugs from the section plan
"""


def build_stage2_user_message(
    plan: StructuralPlan,
    current_section: SectionPlan,
    prior_briefs: list[SectionBrief],
    component_cards: dict[str, dict],
    form: V3InputForm,
) -> str:

    # Format prior briefs — full content, not summarised
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
Voice:              {plan.voice.register_name}, {plan.voice.tone}
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

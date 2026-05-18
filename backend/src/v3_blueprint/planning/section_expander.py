from __future__ import annotations

import json
import uuid

from pydantic_ai import Agent
from pydantic_ai.messages import CachePoint

from contracts.lectio import get_component_card
from core.config import settings
from core.llm.runner import RetryPolicy, run_llm
from generation.v3_studio.dtos import V3InputForm, V3SignalSummary
from v3_blueprint.planning.models import SectionBrief, SectionPlan, StructuralPlan
from v3_execution.config import get_v3_model, get_v3_slot, get_v3_spec

_CALLER = "v3_chunked_architect"
STAGE2_NODE = "v3_stage2_expander"
STAGE2_THINKING = {"type": "adaptive"}
STAGE2_MAX_TOKENS = 1500
STAGE2_CACHE_BETA_HEADER = "extended-cache-ttl-2025-04-11"


def build_stage2_system_prompt() -> str:
    return """You are a lesson elaborator.

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

You have been given the briefs from all prior sections.
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

  - Add a component not in the section plan
  - Remove a planned component
  - Change a component's slug or position
  - Write question prompt text for a question not assigned
    to this section in the question_plan
  - Add a visual_strategy to a section where
    visual_required is false
  - Change the temperature of any question
  - Introduce a concept the plan did not allocate to this section

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Output ONLY valid JSON matching this schema.
Do not add any keys not shown.

{
  "section_id": "must match the section you were given",

  "components": [
    {
      "component_id": "slug from the section plan — unchanged",
      "content_intent": "your writer brief — specific, actionable,
                         within component capacity, max 300 chars"
    }
  ],

  "question_briefs": [
    {
      "question_id": "from question_plan — only questions assigned to this section",
      "prompt_text": "the exact question the student sees",
      "expected_answer": "concise correct answer for answer key"
    }
  ],

  "visual_strategy": null
}

If visual_required is true for this section, replace null with:
{
  "subject": "what the visual depicts — one sentence",
  "type_hint": "diagram | chart | illustration | comparison",
  "anchor_link": "how this visual connects to the anchor example",
  "must_show": ["label 1", "label 2"],
  "must_not_show": ["anything that would distract or mislead"]
}

HARD RULES:
- question_briefs is an empty list [] if no questions are assigned to this section
- visual_strategy is null if visual_required is false for this section
- visual_strategy must be populated if visual_required is true
- component_id values must exactly match slugs from the section plan
- content_intent max 300 chars
- Do not add JSON keys not shown above
"""


def build_stage2_user_message(
    plan: StructuralPlan,
    current_section: SectionPlan,
    prior_briefs: list[SectionBrief],
    component_cards: dict[str, dict],
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
                if brief.question_briefs:
                    prior_block += "    Questions:\n"
                    for qb in brief.question_briefs:
                        prior_block += (
                            f"      {qb.question_id}: {qb.prompt_text}\n"
                        )

    # Format full section sequence — so Stage 2 knows where this section sits
    sequence_lines = []
    for s in plan.sections:
        marker = "→" if s.id == current_section.id else " "
        sequence_lines.append(
            f"  {marker} [{s.role.upper()}] {s.id}: {s.title}"
        )
    sequence_block = "\n".join(sequence_lines)

    # Format question plan — filtered to this section
    my_questions = [
        q for q in plan.question_plan
        if q.section_id == current_section.id
    ]
    q_block = ""
    if my_questions:
        q_block = "QUESTIONS ASSIGNED TO THIS SECTION:\n"
        for q in my_questions:
            q_block += (
                f"  {q.question_id}: temperature={q.temperature}, "
                f"diagram_required={q.diagram_required}\n"
            )
    else:
        q_block = "QUESTIONS ASSIGNED TO THIS SECTION: none\n"

    # Format pitfalls relevant to this section
    pitfall_block = ""
    section_slugs = {c.slug for c in current_section.components}
    relevant_pitfalls = [
        p for p in plan.known_pitfalls
        if p.component_id in section_slugs
    ]
    if relevant_pitfalls:
        pitfall_block = "KNOWN PITFALLS TO ADDRESS IN THIS SECTION:\n"
        for p in relevant_pitfalls:
            pitfall_block += f"  {p.component_id}: {p.misconception}\n"

    return f"""LESSON PLAN
———————————————————————————————————————————————
Goal:               {plan.lesson_intent.goal}
Structure rationale:{plan.lesson_intent.structure_rationale}
Lesson mode:        {plan.lesson_mode}
Anchor:             {plan.anchor.example}
Anchor reuse:       {plan.anchor.reuse_scope}
Voice:              {plan.voice.register_name}, {plan.voice.tone}
Lenses:             {", ".join(e.lens_id for e in plan.applied_lenses)}
Lens effects:       {"; ".join(eff for lens in plan.applied_lenses for eff in lens.effects)}
Prior knowledge:    {", ".join(plan.prior_knowledge)}

FULL SECTION SEQUENCE (your section is marked →):
{sequence_block}

{q_block}
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
) -> list[str | CachePoint]:
    return [
        signals.model_dump_json(),
        form.model_dump_json(),
        json.dumps(resource_spec),
        plan.model_dump_json(),
        CachePoint(ttl="1h"),
    ]


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
    node = STAGE2_NODE
    tid = trace_id or generation_id or str(uuid.uuid4())
    model = get_v3_model(node)
    spec = get_v3_spec(node)
    slot = get_v3_slot(node)
    agent = Agent(
        model=model,
        output_type=SectionBrief,
        system_prompt=build_stage2_system_prompt(),
    )
    section_message = build_stage2_user_message(
        plan=plan,
        current_section=section,
        prior_briefs=prior_briefs,
        component_cards=component_cards,
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
        ),
        section_message,
    ]

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
        model_settings={
            "anthropic_thinking": STAGE2_THINKING,
            "max_tokens": STAGE2_MAX_TOKENS,
            "extra_headers": {"anthropic-beta": STAGE2_CACHE_BETA_HEADER},
        },
        retry_policy=RetryPolicy(
            max_attempts=1,
            call_timeout_seconds=float(settings.v3_timeout_stage2_section_seconds),
        ),
    )
    raw = result.output
    if isinstance(raw, SectionBrief):
        return raw
    if hasattr(raw, "model_dump"):
        return SectionBrief.model_validate(raw.model_dump())
    return SectionBrief.model_validate(raw)


__all__ = [
    "STAGE2_CACHE_BETA_HEADER",
    "STAGE2_MAX_TOKENS",
    "STAGE2_NODE",
    "STAGE2_THINKING",
    "_call_stage2_section",
    "_load_component_cards_for_section",
    "build_stage2_system_prompt",
    "build_stage2_user_message",
]

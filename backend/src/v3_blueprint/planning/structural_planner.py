from __future__ import annotations

import json
import uuid

from pydantic_ai import Agent

from core.config import settings
from core.llm.runner import RetryPolicy, run_llm
from generation.v3_studio.dtos import V3InputForm, V3SignalSummary
from generation.v3_studio.prompts import _planner_index_block, build_v3_shared_prefix
from v3_blueprint.planning.models import StructuralPlan
from v3_blueprint.planning.validators import _allowed_roles_from_resource_spec
from v3_execution.config import get_v3_model, get_v3_model_settings, get_v3_slot, get_v3_spec
from v3_execution.llm_helpers import structured_output_type_for_model

_CALLER = "v3_chunked_architect"
STAGE1_NODE = "v3_stage1_planner"


def build_stage1_system_prompt() -> str:
    shared_prefix = build_v3_shared_prefix()
    planner_block = _planner_index_block()

    return f"""{shared_prefix}
You are a lesson architect. Produce only valid StructuralPlan JSON.

You do NOT write lesson prose, question text, or finished component content.
Your job is to decide concept cards, plain sections, continuity, section flow,
slot choices, and question placement.

{planner_block}

CONSTRAINT: Each section_field (shown in brackets) may appear at most once per section.
Never plan two components with the same section_field in the same section.

REASONING STEPS — work through these in order before producing JSON

STEP 1 — RESTATE
  Restate the learner group and lesson_mode from the signals.
  Do not re-derive them. Keep this to one line.

STEP 2 — GOAL
  Write one testable goal:
  "By the end the student can ___."

STEP 3 — SPEC GATE
  Read the resource spec in your context.
  State required roles and forbidden components.
  Remove anything the spec forbids before continuing. This is a gate.

STEP 4 — ANCHOR
  Choose one concrete anchor example for the whole lesson.
  Name it exactly and explain how it recurs across sections.
  Never substitute or generalise it later.

STEP 5 — CONCEPT CARDS AND PLAIN SECTIONS
  Split the lesson into CARD and PLAIN sections.
  A CARD teaches exactly one concept. Give it one objective phrased as an
  observable capability: something a learner can demonstrate in their work.
  Never use vague objectives such as "understand", "learn about", or
  "appreciate". If an objective joins two different capabilities, split it.

  Give each card 2-4 misconceptions that are specific beliefs a learner would
  confidently act on, not slips, carelessness, or general confusion. If there
  is genuinely no known misconception, emit an empty list and set
  no_known_misconceptions=true. Never pad a list.

  A PLAIN section does not teach a concept: hooks, summaries, and review
  spreads are plain. Set card_id=null. Plain sections have no objective and no
  misconceptions.

  Card ids use {{subject}}.{{topic}}.{{concept}}: lowercase, dots, no spaces,
  and unique within this plan.

STEP 6 — SECTION SEQUENCE
  List sections in order: all required roles plus any optional roles that fit.
  Emit role using the exact role strings allowed by the active resource spec.
  Do not emit phase words as roles.
  For each section after the first, write one transition_note stating what the
  prior section established and what this section now does with it.

STEP 7 — SLOT MAPPING
  For each section, choose components only from that role's preferred or allowed
  set in the resource spec.
  Never use a forbidden component.
  No two components may share a section_field within one section.
  Each purpose must tell the writer exactly what the component must do now.

STEP 8 — VISUALS & QUESTIONS
  Visuals: mark visual_required only where the concept needs spatial or
  relational structure.
  Questions: follow this lesson_mode arc:
    first_exposure → warm and medium only
    consolidation  → medium to cold; at least one transfer
    repair         → warm only until the fault line is resolved
    retrieval      → cold and transfer; no warm
    transfer       → transfer; cold acceptable; no warm or medium
  Keep question counts within the resource spec depth limits.

STEP 9 — SELF CHECK
  Verify:
  - every section has components that can carry its role
  - every emitted role exists in the active resource spec
  - the anchor appears by exact name where the concept is taught
  - question temperatures match lesson_mode
  - no two components in any section share a section_field
  - transition_notes are specific, first section only has null
  - repair_focus is present if lesson_mode=repair

Output ONLY valid JSON matching this schema exactly:
{{
  "lesson_mode": "first_exposure",
  "lesson_intent": {{
    "goal": "By the end of this lesson the student can...",
    "structure_rationale": "Why this structure fits this class and concept."
  }},
  "anchor": {{
    "example": "splitting a pizza into 8 equal slices",
    "reuse_scope": "introduced in intro; reused in explain; varied in practice; returned in summary"
  }},
  "voice": {{
    "register_name": "simple",
    "tone": "encouraging",
    "notation": "Use simple fraction notation and the term denominator."
  }},
  "prior_knowledge": ["equal sharing", "basic division"],
  "repair_focus": null,
  "cards": [
    {{
      "id": "math.fractions.compare",
      "title": "Comparing fractions",
      "objective": "compare two fractions and justify which is larger",
      "prereqs": ["equal sharing", "basic division"],
      "misconceptions": [
        {{
          "id": "M1",
          "description": "a larger denominator always means a larger fraction",
          "source": "drafted"
        }}
      ],
      "no_known_misconceptions": false,
      "opens_by": "returning to the equal pizza slices"
    }}
  ],
  "sections": [
    {{
      "id": "intro",
      "title": "What do you already know about sharing equally?",
      "role": "intro",
      "card_id": null,
      "visual_required": false,
      "transition_note": null,
      "components": [
        {{
          "slug": "hook-hero",
          "purpose": "surface the anchor problem before any instruction"
        }}
      ]
    }},
    {{
      "id": "compare",
      "title": "Compare the slices",
      "role": "explain",
      "card_id": "math.fractions.compare",
      "visual_required": true,
      "transition_note": "The sharing example is now used to compare fraction size.",
      "components": [
        {{
          "slug": "explanation-block",
          "purpose": "build a visual comparison from the shared pizza anchor"
        }},
        {{
          "slug": "pitfall-alert",
          "purpose": "confront the larger-denominator belief"
        }}
      ]
    }}
  ],
  "question_plan": [
    {{
      "question_id": "q1",
      "section_id": "compare",
      "temperature": "warm",
      "diagram_required": false
    }}
  ],
  "answer_key_style": "brief_explanations"
}}

HARD RULES:
- Only use slugs from AVAILABLE COMPONENTS. Never invent slugs.
- Max 6 sections.
- Max 4 component slugs per section.
- transition_note is null for the first section only.
- Every emitted role must exist in the active resource spec.
- Every non-null section card_id resolves to exactly one card.
- Card and misconception ids are unique within their owning scope.
- A card has 2-4 real misconceptions, or explicitly sets
  no_known_misconceptions=true with an empty list.
- Plain sections use card_id=null.
- repair_focus is null unless lesson_mode is repair.
- Do not include content_intent, question prompt text, or visual subject descriptions.
- Do not add any JSON keys not shown in the schema above.
"""


def build_stage1_user_message(
    *,
    signals: V3SignalSummary,
    form: V3InputForm,
    resource_spec: dict,
    previous_errors: list[str] | None = None,
) -> str:
    payload = (
        f"Signals JSON:\n{signals.model_dump_json(indent=2)}\n\n"
        f"Form JSON:\n{form.model_dump_json(indent=2)}\n\n"
        f"RESOURCE SPEC JSON:\n{json.dumps(resource_spec, indent=2, sort_keys=True)}"
    )
    if previous_errors:
        payload += (
            "\n\nVALIDATION ERRORS FROM PREVIOUS ATTEMPT "
            "(fix all of these):\n"
            + "\n".join(f"- {error}" for error in previous_errors)
        )
    return payload


def _validate_stage1_roles(plan: StructuralPlan, resource_spec: dict) -> None:
    allowed_roles = _allowed_roles_from_resource_spec(resource_spec)
    if not allowed_roles:
        return
    for section in plan.sections:
        if section.role not in allowed_roles:
            raise ValueError(
                f"Section '{section.id}' emitted role '{section.role}' "
                f"which is not in the active resource spec roles: {sorted(allowed_roles)}."
            )


async def _call_stage1(
    signals: V3SignalSummary,
    form: V3InputForm,
    resource_spec: dict,
    *,
    trace_id: str | None = None,
    generation_id: str | None = None,
    previous_errors: list[str] | None = None,
) -> StructuralPlan:
    import traceback
    try:
        node = STAGE1_NODE
        tid = trace_id or generation_id or str(uuid.uuid4())
        model = get_v3_model(node)
        spec = get_v3_spec(node)
        slot = get_v3_slot(node)
        agent = Agent(
            model=model,
            output_type=structured_output_type_for_model(StructuralPlan, spec=spec),
            system_prompt=build_stage1_system_prompt(),
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
        )
        raw = result.output
        if isinstance(raw, StructuralPlan):
            plan = raw
        elif hasattr(raw, "model_dump"):
            plan = StructuralPlan.model_validate(raw.model_dump())
        else:
            plan = StructuralPlan.model_validate(raw)
        _validate_stage1_roles(plan, resource_spec)
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

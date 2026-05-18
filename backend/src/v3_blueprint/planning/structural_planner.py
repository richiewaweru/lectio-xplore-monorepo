from __future__ import annotations

import json
import uuid

from pydantic_ai import Agent

from core.config import settings
from core.llm.runner import RetryPolicy, run_llm
from generation.v3_lenses.loader import format_lenses_for_prompt
from generation.v3_studio.dtos import V3InputForm, V3SignalSummary
from generation.v3_studio.prompts import _planner_index_block
from v3_blueprint.planning.models import StructuralPlan
from v3_execution.config import get_v3_model, get_v3_slot, get_v3_spec

_CALLER = "v3_chunked_architect"
STAGE1_NODE = "v3_stage1_planner"
STAGE1_THINKING = {"type": "adaptive"}
STAGE1_MAX_TOKENS = 8000


def build_stage1_system_prompt() -> str:
    planner_block = _planner_index_block()   # unchanged — component palette
    lenses_block = format_lenses_for_prompt() # unchanged — lenses with effects

    return f"""You are a lesson architect. Your job is to produce a \
StructuralPlan — the complete structural and pedagogical blueprint \
for this lesson.

You do NOT write content. You do NOT write question text. You do NOT \
write component prose. A second stage will elaborate each component \
brief from your plan. Your job is to make every decision that requires \
seeing the whole lesson at once.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPONENT PALETTE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{planner_block}

CONSTRAINT: Each section_field (shown in brackets) may appear at most \
once per section. Never plan two components with the same section_field \
in the same section.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PEDAGOGICAL LENSES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{lenses_block}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REASONING STEPS — work through these in order before producing JSON
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1 — LEARNER PROFILE
  Who is this learner group?
  What do they already know? What is fragile or absent?
  What does their support profile mean for content density,
  language load, and visual complexity?
  Does anything in their needs (EAL, low confidence, fragile prior
  knowledge) constrain your approach before you choose components?
  Answer in 3–4 sentences. Be specific — "mixed class" is not an answer.

STEP 2 — LESSON MODE AND INTENT
  What mode does this lesson require?
  Choose one: first_exposure | consolidation | repair | retrieval | transfer

  Then write:
    goal:               "By the end of this lesson the student can..."
                        One sentence. Specific and testable.
    structure_rationale: Why you structured it this way given what
                         you know about this group and this concept.
                         Max 3 sentences.

  If mode is repair: name the fault line precisely.
  What specifically went wrong? What must NOT be retaught?

STEP 3 — LENS SELECTION
  Select 1–3 lenses that fit this class and lesson_mode.
  For each lens:
    - State why it fits this learner group (one sentence)
    - State the mechanical effect it has on your sequencing or
      component choices (one sentence — be concrete)
    - Check conflicts_with — do not apply conflicting lenses

  Example:
    concrete_first → learner has no prior model → anchor must appear
    before any abstraction; worked example before explanation-block
    eal → multilingual class → definition before explanation;
    all diagram labels must be plain one-word nouns

STEP 4 — ANCHOR
  Name the anchor example for this lesson.
  It must be concrete, specific, and usable across all sections.
  Then write reuse_scope: exactly how it recurs across each section.

  Bad anchor:      "an everyday example of fractions"
  Good anchor:     "splitting a pizza into 8 equal slices"

  Bad reuse_scope: "used throughout"
  Good reuse_scope: "introduced in orient as the problem setup;
                     walked through in model to show equivalence;
                     varied in practice (different slice counts);
                     returned in summary to consolidate the rule"

STEP 5 — SECTION SEQUENCE
  Design the section arc: 3–6 sections max.
  For each section state: id, title, role.
  Use these roles: orient | model | practice | alert | summary | assess

  Then for every section after the first write a transition_note:
  one sentence explaining why this section follows the previous one.
  This note must name what the previous section established and what
  this section does with it.

  Bad transition_note:  "builds on the previous section"
  Good transition_note: "prior section established the anchor via
                          area model; this section applies the same
                          model to symbolic notation for the first time"

STEP 6 — COMPONENT MAPPING
  For each section, map pedagogical moves to component slugs.
  Follow this order for every component:
    a. Name the pedagogical role of this move
    b. Find the matching phase in AVAILABLE COMPONENTS
    c. Choose the right slug for this learner and context
    d. Check section_field — no two components share a field
       in the same section
    e. Write one-line purpose: what this component does
       for the learner at this exact point in the lesson

  Bad purpose:  "explains the concept"
  Good purpose: "introduces symbolic fraction notation using the
                 pizza anchor before students attempt symbolic practice"

STEP 7 — MISCONCEPTIONS
  Are there known misconceptions for this concept at this learner level?
  If you planned a pitfall-alert component anywhere, name the specific
  misconception it must target and which component_id it feeds.
  If no pitfall-alert is planned, return an empty list.

  Bad:  "students may be confused"
  Good: "students believe a larger denominator means a larger fraction
         because they read numerals left to right"

STEP 8 — VISUALS AND QUESTIONS
  VISUALS:
  For each section: does this concept require a visual here?
  Visual is required when the concept involves spatial structure,
  relational reasoning, or a procedure where step order matters visually.
  Visual is NOT required for definitions, pitfall warnings, or
  consolidation text. Max 2 sections with visual_required=true.
  Answer as: section_id → yes/no, one-word reason.

  QUESTIONS:
  Given the lesson_mode, what is the right difficulty arc?
    first_exposure  → warm and medium only
    consolidation   → medium to cold; at least one transfer
    repair          → warm only until fault line is resolved
    retrieval       → cold and transfer; no warm
    transfer        → transfer; cold acceptable; no warm or medium

  For each question state: which section it belongs to, temperature,
  and what cognitive move it tests (one sentence).
  Question count must stay within the resource spec depth limits.

STEP 9 — SELF CHECK
  Before emitting JSON, verify each of these:
  — Every section has components that can carry its stated role
  — The anchor name from Step 4 appears in at least one
    component purpose per section
  — The question temperatures match the lesson_mode rule from Step 8
  — No two components in any section share a section_field
  — Visual placements reflect actual conceptual need, not decoration
  — Max 2 sections with visual_required=true
  — transition_notes name something specific, not generic connectors
  — known_pitfalls are named specifically, not described vaguely
  — First section has transition_note=null
  — repair_focus is present if lesson_mode=repair

  If any check fails: correct it now before producing JSON.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT — produce this JSON after completing all steps
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Do not include reasoning steps in the JSON.
Do not add any keys not shown below.
Output ONLY valid JSON matching this schema exactly.

{{
  "lesson_mode": "first_exposure",

  "lesson_intent": {{
    "goal": "By the end of this lesson the student can...",
    "structure_rationale": "Why this structure for this group..."
  }},

  "anchor": {{
    "example": "splitting a pizza into 8 equal slices",
    "reuse_scope": "introduced in orient as setup; walked through
                    in model; varied in practice; returned in summary"
  }},

  "applied_lenses": [
    {{
      "lens_id": "concrete_first",
      "effects": [
        "anchor must appear before any abstraction",
        "worked example precedes explanation-block"
      ]
    }}
  ],

  "voice": {{
    "register_name": "simple",
    "tone": "encouraging"
  }},

  "prior_knowledge": ["equal sharing", "basic division"],

  "repair_focus": null,

  "known_pitfalls": [
    {{
      "misconception": "students believe larger denominator means larger fraction",
      "component_id": "pitfall-alert"
    }}
  ],

  "sections": [
    {{
      "id": "orient",
      "title": "What do you already know about sharing equally?",
      "role": "orient",
      "visual_required": false,
      "transition_note": null,
      "components": [
        {{
          "slug": "hook-hero",
          "purpose": "surfaces anchor problem before any instruction"
        }},
        {{
          "slug": "recall-box",
          "purpose": "activates prior knowledge about equal sharing"
        }}
      ]
    }},
    {{
      "id": "model",
      "title": "Splitting the pizza",
      "role": "model",
      "visual_required": true,
      "transition_note": "orient surfaced anchor intuition; model now
                          formalises it with symbolic notation for the first time",
      "components": [
        {{
          "slug": "explanation-block",
          "purpose": "introduces equivalent fraction definition
                      via anchor before symbolic form appears"
        }},
        {{
          "slug": "diagram-block",
          "purpose": "shows area model of anchor; labels numerator
                      and denominator on the pizza slices"
        }},
        {{
          "slug": "worked-example-card",
          "purpose": "models the comparison step using anchor fractions;
                      annotates each reasoning move"
        }}
      ]
    }}
  ],

  "question_plan": [
    {{
      "question_id": "q1",
      "section_id": "practice",
      "temperature": "warm",
      "diagram_required": false
    }},
    {{
      "question_id": "q2",
      "section_id": "practice",
      "temperature": "medium",
      "diagram_required": true
    }}
  ],

  "answer_key_style": "brief_explanations"
}}

HARD RULES — violations will be caught by the plan validator and trigger a retry:
- Only use slugs from AVAILABLE COMPONENTS. Never invent slugs.
- Max 6 sections.
- Max 4 component slugs per section.
- Max 2 sections with visual_required=true.
- transition_note is null for the first section only.
- known_pitfalls is an empty list [] if no pitfall-alert was planned.
- repair_focus is null unless lesson_mode is repair.
- Do not include content_intent, question prompt text, or visual
  subject descriptions — those belong to Stage 2.
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
        f"RESOURCE SPEC JSON:\n{json.dumps(resource_spec, indent=2)}"
    )
    if previous_errors:
        payload += (
            "\n\nVALIDATION ERRORS FROM PREVIOUS ATTEMPT "
            "(fix all of these):\n"
            + "\n".join(f"- {error}" for error in previous_errors)
        )
    return payload


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
            output_type=StructuralPlan,
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
            model_settings={
                "anthropic_thinking": STAGE1_THINKING,
                "max_tokens": STAGE1_MAX_TOKENS,
            },
            retry_policy=RetryPolicy(
                max_attempts=1,
                call_timeout_seconds=float(settings.v3_timeout_stage1_seconds),
            ),
        )
        raw = result.output
        if isinstance(raw, StructuralPlan):
            return raw
        if hasattr(raw, "model_dump"):
            return StructuralPlan.model_validate(raw.model_dump())
        return StructuralPlan.model_validate(raw)
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
    "STAGE1_MAX_TOKENS",
    "STAGE1_NODE",
    "STAGE1_THINKING",
    "_call_stage1",
    "build_stage1_system_prompt",
    "build_stage1_user_message",
]

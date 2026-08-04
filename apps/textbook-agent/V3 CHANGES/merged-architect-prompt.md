# Merged Architect System Prompt
## `REASONING_SCAFFOLD` + resource spec gate + phase-first component search

**File to update:** `backend/src/generation/v3_studio/prompts.py`

This document shows the exact replacement for:
- The `REASONING_SCAFFOLD` constant
- The `build_architect_system_prompt()` return string
- The `agents.py` user prompt construction

Read the full document before touching any code.

---

## What changed and why

| Element | Old | New | Reason |
|---|---|---|---|
| Step 1 — LEARNER | ✅ Keep as-is | Kept | Correctly locks who the class is before any planning |
| Step 2 — CONCEPT | ✅ Keep as-is | Kept | "Single hardest step" and misconception framing is exactly right |
| Step 3 — SEQUENCE | ✅ Keep verb phrase format | Kept + improved | Added lens-informed sequencing |
| Step 4 — COMPONENTS | Jumps straight to slug | Phase-first: role → phase → slug | Without phase reasoning the architect skips the pedagogical question |
| Step 5 — VISUALS | ✅ Keep yes/no format | Kept | Right level of specificity |
| Step 6 — QUESTIONS | ✅ Keep one-sentence-per-Q | Kept + mode-aware temperatures | Adds lesson_mode → temperature constraint |
| Resource spec gate | Missing | Added as Step 0 | Architect had no structural definition of what the resource type IS |
| Lens selection | Passive — listed in prompt | Active — Step 2.5 explicitly selects | Lenses were applied generically; now selected before sequencing |
| Rules block | Grab-bag list | Structured output rules | References the reasoning steps; no redundancy |
| resource_type enum in rules | `lesson\|mini_booklet` only | Removed — spec defines it | The spec in the user prompt is the authority |

---

## Step 1 — Replace `REASONING_SCAFFOLD` constant in `prompts.py`

Find the existing `REASONING_SCAFFOLD` string constant. Delete it entirely and replace with:

```python
REASONING_SCAFFOLD = """
━━━ REASONING STEPS — work through these before writing any JSON ━━━━━━━━━━━━

Do not skip ahead. Each step locks a decision that the next step depends on.
Keep answers short. You are building toward the blueprint, not writing an essay.

STEP 1 — LEARNER CONTEXT
  Who is this class? What is their level and what are their main barriers?
  What does their support profile mean for content density and visual load?
  Does anything in their needs (EAL, low confidence, fragile prior knowledge)
  require a specific approach before you choose components?
  (Answer in 2–3 sentences. Be specific — "mixed class" is not an answer.)

STEP 2 — CONCEPT AND DIFFICULTY
  What is the core concept in one sentence?
  What is the single hardest step for this learner to understand?
  What misconception most commonly arises here, and does it need a pitfall section?
  (Answer in 3 sentences.)

STEP 2.5 — LENS SELECTION
  From the pedagogical lenses in your context, select 1–3 that fit this class.
  For each chosen lens, state: lens_id, why it fits (one sentence), and
  what specific effect it will have on your sequencing or component choices.
  Check conflicts_with — do not apply lenses that conflict with each other.
  (Answer as: lens_id → why → effect on plan.)

  Example:
    first_exposure → learner has no prior model → keep anchor constant across
                     all sections; warm questions only; model before practice
    eal           → multilingual class → definition-card before explanation-block;
                     label all diagram elements; no idiom in question stems

STEP 3 — RESOURCE STRUCTURE
  Read the RESOURCE SPEC in your context window.
  State: what is this resource type for, what is forbidden, what sections are required.
  If a section you wanted to plan is forbidden by the spec, remove it now.
  (Answer as: purpose / forbidden / required sections list.)

  This step is a gate. If you plan a component that the spec forbids,
  the output is wrong. Check forbidden_components before proceeding.

STEP 4 — TEACHING SEQUENCE
  Given the lesson_mode, learner_level, and the lens effects from Step 2.5,
  write the teaching sequence as an ordered list of 4–6 moves.
  Each move is one verb phrase: "Orient the learner to...", "Explain how to...",
  "Model with...", "Practice...".
  Apply lens effects here: if a lens says "lead with a worked example", put Model
  before Understand. If a lens says "define terms first", put Understand before
  Explain. The sequence should reflect how a good teacher would actually order this.
  (Answer as a numbered list.)

STEP 5 — COMPONENT MAPPING (phase-first)
  Map each sequence move to one component slug.
  Follow this order for every move:
    a. Name the pedagogical role of this move
       (orient / understand / model / practice / alert / visual / simulate)
    b. Find the phase in the AVAILABLE COMPONENTS that matches that role
    c. Choose the right component from that phase for this learner and context
    d. Check section_field — no two components with the same field in one section
  (Answer as: move → role → phase → slug [field].)

  Example:
    "Explain how to find equivalent fractions"
    → role: understand → Phase 2 — Understand
    → slug: explanation-block [explanation]

STEP 6 — VISUALS
  For each section, answer yes or no: does this concept require visual support here?
  Spatial and procedural steps usually need visuals.
  Definitions and pitfall warnings usually do not.
  Check resource spec visual policy — some resource types restrict visuals.
  (Answer as: section_id → yes/no, one word reason.)

STEP 7 — QUESTIONS
  Given the lesson_mode, what is the right difficulty progression?
  lesson_mode → allowed temperatures:
    first_exposure  → warm and medium only (no cold for below-average groups)
    consolidation   → start medium, reach cold and transfer
    repair          → warm only at first; cold only after pitfall is resolved
    retrieval       → cold and transfer; no warm unless very fragile
    transfer        → transfer questions; cold acceptable; no warm or medium

  For each planned question, write one sentence: difficulty, what cognitive
  move it tests, whether it needs a diagram.
  Question count must stay within the depth limits in the resource spec.
  (Answer as: Q1 warm — tests recall of...; Q2 medium — requires application of...)

Now produce the ProductionBlueprint JSON exactly matching the schema.
Do not include the reasoning steps in the JSON output.
"""
```

---

## Step 2 — Update `build_architect_system_prompt()` return string

Replace the entire `return f"""..."""` block in `build_architect_system_prompt()` with:

```python
    return f"""You are a lesson architect. Output ONLY a valid ProductionBlueprint matching the schema.

{manifest_block}

CONSTRAINT: Each section_field (shown in brackets above) may appear at
most once per section. Never plan two components with the same
section_field in the same section.
{budget_rules}{section_rules}

{lenses_block}

{REASONING_SCAFFOLD}

OUTPUT RULES:
- Only use component slugs from the AVAILABLE COMPONENTS list above. Never invent slugs.
- metadata: version "3.0", title, subject (from form.subject)
- lesson:
    lesson_mode — choose from: first_exposure | consolidation | repair | retrieval | transfer
    resource_type — read from the RESOURCE SPEC in your context window (do not invent)
- applied_lenses: exactly the lenses you selected in Step 2.5, each with lens_id
  and specific non-empty effects drawn from your Step 2.5 reasoning.
  Bad effect: "use clear language"
  Good effect: "define 'equivalent fraction' before explanation-block; reuse same
               fraction pair across all practice questions"
- voice: register (simple|balanced|formal), optional tone — match to learner level
- anchor: reuse_scope string — describe how the anchor example recurs across sections
- sections: each with section_id, title, role, visual_required bool,
  components with slug and content_intent.
  content_intent must be specific enough that a writer can act on it without asking questions.
  Bad:  "explain photosynthesis"
  Good: "explain light-dependent reactions; contrast what happens with and without sunlight;
         use the chloroplast membrane as the anchor structure throughout"
- question_plan: temperature must match lesson_mode guidance from Step 7.
  Each item: question_id, section_id, temperature, prompt, expected_answer, diagram_required.
- visual_strategy: only for sections where visual_required = true.
  Each item: section_id, strategy (what the visual should show), optional density.
- answer_key: style — answers_only | brief_explanations | full_working
- repair_focus: required when lesson_mode = repair.
  fault_line: what specifically went wrong (one sentence).
  what_not_to_teach: list of things to exclude from this lesson.
- teacher_materials and prior_knowledge lists are allowed and encouraged.
Use short, clear section IDs: orient, understand, model, practice, alert, summary."""
```

**Note on migration state:** If `_planner_index_block()` is already in place (from the migration proposal), replace `manifest_block` with `planner_block` and remove the separate `budget_rules`/`section_rules` variables — they are included inside `_planner_index_block()`. The rest of the return string is identical.

---

## Step 3 — Inject resource spec into user prompt in `agents.py`

**File:** `backend/src/generation/v3_studio/agents.py`

Find `generate_production_blueprint()`. The current user prompt construction is:

```python
    clar = clarification_answers or []
    clar_txt = "\n".join(f"Q: {c.question}\nA: {c.answer}" for c in clar)
    user = (
        f"Signals:\n{signals.model_dump_json(indent=2)}\n\n"
        f"Form:\n{form.model_dump_json(indent=2)}\n\n"
        f"Clarifications:\n{clar_txt or '(none)'}"
    )
```

Replace with:

```python
    clar = clarification_answers or []
    clar_txt = "\n".join(f"Q: {c.question}\nA: {c.answer}" for c in clar)

    # Resolve and render the resource spec for the inferred resource type.
    # This is injected per-request (not in the system prompt) because the
    # resource type varies per teacher request.
    resource_spec_block = _render_resource_spec(
        inferred_resource_type=signals.inferred_resource_type,
        duration_minutes=form.duration_minutes,
    )

    user = (
        f"Signals:\n{signals.model_dump_json(indent=2)}\n\n"
        f"Form:\n{form.model_dump_json(indent=2)}\n\n"
        f"Clarifications:\n{clar_txt or '(none)'}\n\n"
        f"RESOURCE SPEC — treat structural rules as hard constraints:\n"
        f"{resource_spec_block}"
    )
```

Add the `_render_resource_spec()` helper to `agents.py`, just above `generate_production_blueprint()`:

```python
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

    # Graceful fallback if the inferred type has no spec
    available = list_spec_ids()
    if resource_type not in available:
        resource_type = "lesson"

    depth = "quick" if duration_minutes < 20 else "deep" if duration_minutes > 45 else "standard"

    try:
        spec = get_spec(resource_type)
        return render_spec_for_prompt(
            spec,
            depth=depth,
            active_roles=[],      # architect decides roles — do not pre-filter
            active_supports=[],   # no support signals at this stage
        )
    except Exception:
        return (
            f"Resource type: {resource_type}\n"
            "(No detailed spec available for this type — use judgment based on resource intent.)"
        )
```

Add these imports at the top of `agents.py` if not already present:

```python
# These are imported inside _render_resource_spec() to avoid circular imports
# at module load time. No top-level import needed.
```

The imports are inside the function body, so no top-level change is needed.

---

## Step 4 — Update `SIGNAL_SYSTEM` to align with new resource types

**File:** `backend/src/generation/v3_studio/prompts.py`

The current `SIGNAL_SYSTEM` sets `inferred_resource_type` to only `lesson` or `mini_booklet`. Expand it to match the full resource type list that has specs:

```python
SIGNAL_SYSTEM = """You extract structured teaching signals from a structured teacher form.

The form already provides lesson_mode, learner_level, support_needs, prior_knowledge_level,
intended_outcome, grade_level, subject, duration_minutes, topic, and subtopics.

Do NOT re-infer these from free text. Read them directly from the form fields.

Your job:
- Confirm the teaching topic (short, specific).
- Optionally select ONE subtopic string (or null) if the form subtopics are empty or too broad.
- Summarise teacher_goal in one clear sentence.
- Set inferred_resource_type to one of:
    lesson            — default; full instructional lesson
    mini_booklet      — compact guided learning
    worksheet         — practice resource; concept already taught
    quiz              — formal assessment
    exit_ticket       — short end-of-lesson check
    practice_set      — drill-style repetition
    quick_explainer   — focused concept clarification
  Default to lesson if the teacher's intent does not clearly match another type.
- Populate missing_signals ONLY if topic is genuinely ambiguous or contradictory.
"""
```

---

## Verification

After all changes are applied:

```bash
uv run python -c "
from generation.v3_studio.prompts import build_architect_system_prompt, REASONING_SCAFFOLD

prompt = build_architect_system_prompt()

# Core reasoning steps present
assert 'STEP 1 — LEARNER CONTEXT' in prompt
assert 'STEP 2 — CONCEPT AND DIFFICULTY' in prompt
assert 'STEP 2.5 — LENS SELECTION' in prompt
assert 'STEP 3 — RESOURCE STRUCTURE' in prompt
assert 'STEP 4 — TEACHING SEQUENCE' in prompt
assert 'STEP 5 — COMPONENT MAPPING' in prompt
assert 'STEP 6 — VISUALS' in prompt
assert 'STEP 7 — QUESTIONS' in prompt

# Phase-first language present
assert 'phase-first' in prompt
assert 'role → phase → slug' in prompt

# Lens selection is explicit
assert 'conflicts_with' in prompt
assert 'lens_id → why → effect on plan' in prompt

# Resource spec gate present
assert 'RESOURCE SPEC' in prompt
assert 'forbidden_components' in prompt

# Old bad patterns gone
assert 'resource_type lesson|mini_booklet' not in prompt
assert 'FormLensHints' not in prompt

# Output rules present and specific
assert 'Bad effect' in prompt
assert 'Good effect' in prompt
assert 'Bad:' in prompt
assert 'Good:' in prompt

print('Merged prompt OK')
print(f'Prompt length: {len(prompt)} chars')
"
```

```bash
uv run pytest backend/tests/generation/test_v3_studio_prompts.py -v
```

---

## The full reasoning chain — what the architect now does, step by step

```
User prompt arrives:
  signals (topic, learner_needs, inferred_resource_type, prior_knowledge...)
  form (year_group, subject, duration, free_text)
  clarifications
  RESOURCE SPEC (rendered from inferred_resource_type + duration)
        ↓
STEP 1 — Lock who the learner is
  → content density decision
  → visual load decision
  → support approach
        ↓
STEP 2 — Lock what's hard about this concept
  → identifies the single cognitive obstacle
  → surfaces likely misconception → decides if pitfall-alert is needed
        ↓
STEP 2.5 — Select lenses
  → checks applies_when against learner context
  → checks conflicts_with between candidates
  → commits to specific effects on the plan (not generic ones)
        ↓
STEP 3 — Read the resource spec
  → locks what the resource IS and what it CANNOT contain
  → records required sections (must appear)
  → records forbidden_components (absolute, no exceptions)
        ↓
STEP 4 — Sequence the moves
  → verb phrases, in order
  → lens effects applied here (e.g. model before understand if lens demands it)
  → lesson_mode shapes the sequence (retrieval → no explanation moves)
        ↓
STEP 5 — Map moves to components (phase-first)
  → each move: name role → find phase → pick slug → check field uniqueness
  → lens effects applied at component level (e.g. definition-card before explanation)
        ↓
STEP 6 — Visual decisions
  → yes/no per section with reason
  → checked against resource spec visual policy
        ↓
STEP 7 — Question plan
  → temperatures constrained by lesson_mode
  → count constrained by resource spec depth limits
  → each question: difficulty + cognitive move + diagram flag
        ↓
ProductionBlueprint JSON
  → applied_lenses reflects Step 2.5 choices with specific effects
  → sections reflect Steps 4+5
  → question_plan reflects Step 7
  → resource_type taken from spec, not invented
```

# Architect Stability Improvements

## Addressing 5 identified issues in the V3 lesson architect

This file started as an **implementation spec**. It now doubles as a **spec vs as-built reference**: the original problems and proposed fixes are preserved for context, and each issue includes **verbatim excerpts** from the current codebase so the doc does not drift.

**As-built status (summary)**

| Issue | Topic | Status |
| --- | --- | --- |
| 1 | `LessonMode` / `ResourceType` in `v3_blueprint/models.py` | **Done.** `LessonMode` matches the original five-value proposal. `ResourceType` was implemented with a **different** expansion (aligned with signals + resource specs): see *As implemented* below — not the appendix `retrieval_practice` / `worked_example_set` names. |
| 2 | Architect prompt reasoning + mode annotations | **Done** via `REASONING_SCAFFOLD`, `_planner_index_block()`, resource spec injection in agents, and `SIGNAL_SYSTEM` — **not** via the single “PLANNING PROTOCOL” return block in Appendix B. |
| 3 | Writer vs media partition in `compile_orders.py` | **Done** (`_EXTERNAL_FIELDS`, `writer_comps`, `component_cards`). |
| 4 | Retry prompt with prior errors | **Done** (`_prior_errors`, `build_section_writer_retry_prompt`; executor uses `component_cards` + `validate_lectio_field_payload`). |
| 5 | Blueprint validation errors in `agents.py` | **Done** (`_validate_blueprint` uses `compiler_result` and formatted lists). |

**Original scope (unchanged intent)**

- **Primary files:** `backend/src/v3_blueprint/models.py`, `backend/src/generation/v3_studio/prompts.py`, `backend/src/v3_execution/compile_orders.py`, `backend/src/v3_execution/executors/section_writer.py`, plus `backend/src/generation/v3_studio/agents.py` (Issue 5).
- **Do not change (original guardrail):** `pipeline/contracts.py`, `v3_review/`, `pipeline/` (v1/v2 path), any frontend files — unless a future change explicitly revisits that boundary.

---

## Contract fidelity — phase names vs pedagogical roles

Lectio’s exported `planner_index.phase_map` uses **contract phase labels** such as **Orient**, **Build Knowledge**, **Practice and Check**, **Address Mistakes**, **Visualize**, etc. Those strings are what `_planner_index_block()` prints as `Phase N — {name}:` in the architect prompt.

Separately, `REASONING_SCAFFOLD` (and the historical Appendix B) use **short pedagogical roles** like *understand*, *practice*, *alert* to structure thinking. Those roles are **not** always one-to-one with the contract’s phase names.

**Rules for humans and future prompt edits**

1. **Slug choice** must respect the **AVAILABLE COMPONENTS** list grouped by **Phase N — {contract name}**. If a component appears under phase 1 **Orient** in the contract (e.g. `explanation-block` in Lectio 0.4.2), the architect must still only pick that slug from the palette the contract exposes — even when the component card’s `cognitive_job` reads like “Build understanding”.
2. Pedagogical **roles** are reasoning vocabulary; **contract phases** are the source of truth for which slugs are valid in which group.
3. **Known tension (no code change in this refresh):** `REASONING_SCAFFOLD` STEP 5 includes an example line `→ Phase 2 — Understand` for `explanation-block`. In the live Lectio 0.4.2 export, phase 2 is **Build Knowledge** and `explanation-block` is listed under **Orient**. Treat that example as **illustrative of the step structure**, not as a guarantee it matches the current `phase_map`. A future prompt edit should realign the example with the synced contract.

---

## Issue 1 — Expand `LessonMode` and `ResourceType` enums

**File:** `backend/src/v3_blueprint/models.py`

### Problem (historical)

`LessonMode` previously had only three values while the architect prompt mentioned `retrieval` and `transfer`. `ResourceType` was too narrow to express quiz-like or practice-only resources.

### Original proposal

See **Appendix A** for the first spec’s `ResourceType` literals (`retrieval_practice`, `worked_example_set`). The codebase **did not** adopt those exact identifiers; it aligned `ResourceType` with **inferred resource types** from the signals step and **resource spec** IDs.

### As implemented (copy-paste reference)

```python
LessonMode = Literal[
    "first_exposure",  # learner meets concept for the first time
    "consolidation",  # revisiting known content to deepen or connect
    "repair",  # targeting a known misconception or gap
    "retrieval",  # low-cue recall practice with minimal new explanation
    "transfer",  # applying understanding to an unfamiliar context
]
QuestionTemperature = Literal["warm", "medium", "cold", "transfer"]
ResourceType = Literal[
    "lesson",  # fallback only — no spec file; architect uses judgment
    "mini_booklet",  # full guided lesson with scaffolding (spec exists)
    "worksheet",  # practice resource; concept already taught (spec exists)
    "quiz",  # formal assessment (spec exists)
    "exit_ticket",  # short end-of-lesson check (spec exists)
    "practice_set",  # drill-style repetition (spec exists)
    "quick_explainer",  # focused concept clarification (spec exists)
]
```

### Verification

```bash
uv run python -c "
from v3_blueprint.models import LessonMode, ResourceType, ProductionBlueprint, LessonModePlan
plan = LessonModePlan(lesson_mode='retrieval', resource_type='quiz')
assert plan.lesson_mode == 'retrieval'
assert plan.resource_type == 'quiz'
print('LessonMode and ResourceType OK')
"
```

---

## Issue 2 — Annotate `lesson_mode` / `resource_type` and add a planning protocol

**File:** `backend/src/generation/v3_studio/prompts.py` (and related: `agents.py` for resource spec text, `SIGNAL_SYSTEM` in the same module)

### Problem (historical)

The architect needed structured reasoning (phase → role → component) and clearer semantics for modes and resource formats.

### What shipped instead of Appendix B

The implementation uses:

- `_planner_index_block()` — phase-grouped slugs from the Lectio contract.
- `REASONING_SCAFFOLD` — multi-step reasoning before JSON.
- `OUTPUT RULES` — schema summary; `resource_type` is **taken from the RESOURCE SPEC in context** (not re-listed as a closed-form legend in the architect prompt).
- `SIGNAL_SYSTEM` — defines `inferred_resource_type` values that match `ResourceType`.

### As implemented — `REASONING_SCAFFOLD` (verbatim)

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

### As implemented — `build_architect_system_prompt()` body (verbatim)

```python
def build_architect_system_prompt() -> str:
    """System prompt for the lesson architect, including live Lectio manifest and lenses."""
    from generation.v3_lenses.loader import format_lenses_for_prompt

    planner_block = _planner_index_block()
    lenses_block = format_lenses_for_prompt()

    return f"""You are a lesson architect. Output ONLY a valid ProductionBlueprint matching the schema.

{planner_block}

CONSTRAINT: Each section_field (shown in brackets above) may appear at
most once per section. Never plan two components with the same
section_field in the same section.

{lenses_block}

{REASONING_SCAFFOLD}

OUTPUT RULES:
- Only use component slugs from the AVAILABLE COMPONENTS list above. Never invent slugs.
- metadata: version "3.0", title, subject (from teacher subject)
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

### Verification

```bash
uv run python -c "
from generation.v3_studio.prompts import build_architect_system_prompt
prompt = build_architect_system_prompt()
assert 'REASONING_SCAFFOLD' not in prompt  # constant name not in string
assert 'REASONING STEPS' in prompt
assert 'STEP 5 — COMPONENT MAPPING' in prompt
assert 'retrieval' in prompt
assert 'resource_type — read from the RESOURCE SPEC' in prompt
print('Prompt OK')
print(f'Prompt length: {len(prompt)} chars')
"
```

---

## Issue 3 — Partition writer vs media components in `compile_orders.py`

**File:** `backend/src/v3_execution/compile_orders.py`

### Problem (historical)

Media components (`diagram-block`, `simulation-block`, …) were included in the section writer’s component list and card dict, wasting context; media is handled via `VisualGeneratorWorkOrder`.

### As implemented (verbatim core loop)

Top-level imports include:

```python
from pipeline.contracts import _EXTERNAL_FIELDS, get_section_field_for_component
```

Section loop (abbreviated only by eliding unrelated work-order fields):

```python
    for sec in blueprint.sections:
        writer_comps: list[WriterSectionComponent] = []
        for c in sec.components:
            canonical = canonical_component_id(c.component)
            field = get_section_field_for_component(canonical)
            if field in _EXTERNAL_FIELDS:
                continue
            writer_comps.append(
                WriterSectionComponent(
                    component_id=canonical,
                    teacher_label=c.component.replace("_", " ").title(),
                    content_intent=c.content_intent,
                )
            )
        if not writer_comps:
            learning_intent = sec.title
        else:
            learning_intent = "; ".join(c.content_intent for c in writer_comps) or sec.title
        wo = SectionWriterWorkOrder(
            work_order_id=f"sec-{sec.section_id}",
            section=WriterSection(
                id=sec.section_id,
                title=sec.title,
                learning_intent=learning_intent,
                constraints=[f"role:{sec.role}"],
                register_notes=[],
                components=writer_comps,
            ),
            register=register,
            learner_profile=LearnerProfileSpec(),
            support_adaptations=[e.effects[0] for e in blueprint.applied_lenses if e.effects],
            source_of_truth=truth,
            consistency_rules=consistency_rules,
            component_cards=_component_cards_for_components(
                [c.component_id for c in writer_comps],
            ),
            template_id=template_id,
        )
        section_orders.append(wo)
```

### Verification

Same as the original doc’s partition simulation (`_EXTERNAL_FIELDS`, `writer_only` / `media_only`); run from repo root with `PYTHONPATH=backend/src` if your environment requires it.

---

## Issue 4 — Feed validation errors back into the retry prompt

**Files:** `backend/src/v3_execution/executors/section_writer.py`, `backend/src/v3_execution/prompts/section_writer.py`

### Problem (historical)

Retries reused the same user prompt with no signal about missing or invalid fields.

### As implemented — executor excerpt (verbatim pattern)

```python
    _prior_errors: list[str] = []

    async def _attempt(already_retried: bool) -> ExecutorOutcome:
        warnings: list[str] = []
        errors: list[str] = []
        try:
            if already_retried and _prior_errors:
                prompt = build_section_writer_retry_prompt(order, _prior_errors)
            else:
                prompt = build_section_writer_prompt(order)
            response = await run_json_agent(
                node_name="v3_section_writer",
                trace_id=trace_id,
                generation_id=generation_id,
                system_prompt="Return compact JSON matching the user's contract.",
                user_prompt=prompt,
                model_overrides=model_overrides,
            )
            # ... field extraction, validate_lectio_field_payload, validate_component_batch ...
            if already_retried and not ok:
                warnings.append("section writer retry unsuccessful")
            if not ok:
                _prior_errors.clear()
                _prior_errors.extend(errors)
            return ExecutorOutcome(ok=ok, blocks=blocks, warnings=warnings, errors=errors)
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
            _prior_errors.clear()
            _prior_errors.extend(errors)
            return ExecutorOutcome(ok=False, warnings=warnings, errors=errors)
```

`validate_component_batch` is called with `component_cards=order.component_cards` (not `manifest_components`).

### As implemented — `build_section_writer_retry_prompt()` (verbatim)

```python
def build_section_writer_retry_prompt(
    order: SectionWriterWorkOrder,
    prior_errors: list[str],
) -> str:
    """
    Build a retry prompt with focused correction guidance.
    """
    base_prompt = build_section_writer_prompt(order)
    error_lines = "\n".join(f"  - {e}" for e in prior_errors[:8])
    correction_block = f"""RETRY CORRECTION — your previous attempt had these problems:
{error_lines}

Fix ONLY the problems listed above. Do not change anything else.
Re-read the LECTIO COMPONENT CONTRACTS below and correct the identified fields.
"""
    first_newline = base_prompt.index("\n")
    return (
        base_prompt[: first_newline + 1]
        + "\n"
        + correction_block
        + "\n"
        + base_prompt[first_newline + 1 :]
    )
```

### Verification

Use `component_cards` on `SectionWriterWorkOrder` (not `manifest_components`):

```bash
uv run python -c "
from v3_execution.models import (
    SectionWriterWorkOrder, WriterSection, WriterSectionComponent,
    RegisterSpec, LearnerProfileSpec,
)
from v3_execution.prompts.section_writer import (
    build_section_writer_retry_prompt,
)
from pipeline.contracts import get_component_card, clear_cache
clear_cache()

card = get_component_card('explanation-block') or {}
order = SectionWriterWorkOrder(
    work_order_id='test-retry',
    section=WriterSection(
        id='s-test',
        title='Test',
        learning_intent='test intent',
        components=[
            WriterSectionComponent(
                component_id='explanation-block',
                teacher_label='Explanation',
                content_intent='explain osmosis',
            )
        ],
    ),
    register=RegisterSpec(),
    learner_profile=LearnerProfileSpec(),
    component_cards={'explanation-block': card},
    template_id='guided-concept-path',
)

prior_errors = [
    'explanation.emphasis: value is not a valid list',
    'Missing field output for practice',
]

retry_prompt = build_section_writer_retry_prompt(order, prior_errors)
assert 'RETRY CORRECTION' in retry_prompt
assert 'explanation.emphasis' in retry_prompt
assert 'Fix ONLY the problems listed above' in retry_prompt
print('Retry prompt OK')
"
```

---

## Issue 5 — Surface blueprint parse errors with useful context

**File:** `backend/src/generation/v3_studio/agents.py`

### Problem (historical)

Malformed blueprints surfaced opaque errors with little structure.

### As implemented (verbatim)

```python
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
```

### Verification

```bash
uv run python -c "
from v3_blueprint.models import (
    ProductionBlueprint, BlueprintMetadata, LessonModePlan,
    AppliedLens, VoicePlan, AnchorPlan, SectionPlan, ComponentPlan,
    QuestionPlanItem, AnswerKeyPlan, VisualStrategyPlan,
)
from v3_blueprint.compiler import BlueprintCompiler

bp = ProductionBlueprint(
    metadata=BlueprintMetadata(version='3.0', title='Test', subject='Maths'),
    lesson=LessonModePlan(lesson_mode='retrieval', resource_type='quiz'),
    applied_lenses=[AppliedLens(lens_id='retrieval', effects=['space recall'])],
    voice=VoicePlan(register='balanced'),
    anchor=AnchorPlan(reuse_scope='entire_resource'),
    sections=[SectionPlan(
        section_id='practice',
        title='Practice',
        role='practice',
        components=[ComponentPlan(component='practice-stack', content_intent='recall fractions')]
    )],
    question_plan=[QuestionPlanItem(
        question_id='q1', section_id='practice',
        temperature='cold', prompt='What is 3/4 of 20?',
        expected_answer='15', diagram_required=False,
    )],
    answer_key=AnswerKeyPlan(style='answers_only'),
    visual_strategy=VisualStrategyPlan(),
)
errors = BlueprintCompiler().compile_all(bp)
print(f'Valid blueprint: errors={errors}')
"
```

---

## Full verification run

```bash
uv run pytest backend/tests/generation/ -v
uv run pytest backend/tests/v3_execution/ -v -k "not integration"
uv run pytest backend/tests/v3_blueprint/ -v
```

### Grep / search checks

Examples below use **Unix** `grep`. On **Windows PowerShell**, use `Select-String` with the same patterns, e.g. `Select-String -Path backend/src/v3_blueprint/models.py -Pattern 'LessonMode|ResourceType'`.

```bash
# Enums
grep -n "LessonMode\|ResourceType" backend/src/v3_blueprint/models.py

# Architect reasoning scaffold (not the historical "PLANNING PROTOCOL" string)
grep -n "REASONING STEPS\|STEP 5\|RESOURCE SPEC" backend/src/generation/v3_studio/prompts.py

# Media partition + component_cards
grep -n "_EXTERNAL_FIELDS\|writer_comps\|component_cards" backend/src/v3_execution/compile_orders.py

# Retry
grep -n "build_section_writer_retry_prompt\|RETRY CORRECTION\|_prior_errors" \
    backend/src/v3_execution/executors/section_writer.py \
    backend/src/v3_execution/prompts/section_writer.py

# Blueprint validation
grep -n "_validate_blueprint\|compiler_result" backend/src/generation/v3_studio/agents.py
```

---

## Summary of what changed and why

| Issue | File(s) | Change | Why |
| --- | --- | --- | --- |
| Missing `lesson_mode` values | `v3_blueprint/models.py` | Added `retrieval`, `transfer` | Align Pydantic with prompt |
| Narrow `resource_type` | `v3_blueprint/models.py` | Added worksheet, quiz, exit_ticket, practice_set, quick_explainer (etc.) | Express formats + match resource specs / signals |
| Architect reasoning | `v3_studio/prompts.py` (+ agents resource spec) | `REASONING_SCAFFOLD`, planner block, OUTPUT RULES | Force structured decisions before JSON |
| Media in writer WO | `v3_execution/compile_orders.py` | Partition with `_EXTERNAL_FIELDS`; `component_cards` for writer only | Keep writer context lean |
| Retry blind | `section_writer` executor + prompts | `_prior_errors` + `build_section_writer_retry_prompt` | Retries target concrete failures |
| Opaque blueprint errors | `v3_studio/agents.py` | `_validate_blueprint` formats `ValidationError` + compiler list | Easier debugging |

---

## Appendix A — Original Issue 1 `ResourceType` proposal (not adopted verbatim)

```python
ResourceType = Literal[
    "lesson",               # full instructional lesson with explanation and practice
    "mini_booklet",         # compact version of a lesson, reduced scaffolding
    "quiz",                 # assessment-first: primarily questions with minimal explanation
    "retrieval_practice",   # spaced recall: questions, no new teaching
    "worked_example_set",   # model-heavy: multiple worked examples with minimal practice
]
```

The living codebase uses the `ResourceType` block in **Issue 1 — As implemented** instead.

---

## Appendix B — Original Issue 2 single-string “PLANNING PROTOCOL” prompt (historical alternative)

This block was the first spec for replacing the architect `Rules:` section. The shipped system uses `_planner_index_block()` + `REASONING_SCAFFOLD` + `OUTPUT RULES` instead; keep this appendix for comparison only.

```python
    return f"""You are a lesson architect. Output ONLY a valid ProductionBlueprint matching the schema.

{manifest_block}

CONSTRAINT: Each section_field (shown in brackets above) may appear at
most once per section. Never plan two components with the same
section_field in the same section.
{budget_rules}{section_rules}

{lenses_block}

PLANNING PROTOCOL — follow this order for every section you plan:

  Step 1. Decide the section's pedagogical role.
          Use the phase names as your guide:
            Orient     → introduce purpose, context, or prior knowledge check
            Understand → build conceptual understanding through language
            Model      → show a procedure or reasoning process in action
            Practice   → apply, retrieve, or check understanding
            Alert      → pre-empt a misconception or flag a common error
            Visual     → carry meaning that requires image or diagram
            Simulate   → interactive or exploratory engagement

  Step 2. Choose components only from the phase that matches your chosen role.
          Do not mix phases within a single section unless you have a clear reason.

  Step 3. Write a content_intent that is specific enough to guide the writer.
          Bad:  "explain photosynthesis"
          Good: "explain the light-dependent reactions, contrasting what happens
                 with and without sunlight, using the chloroplast as the anchor"

  Step 4. Check: does any other section in this blueprint already use the same
          section_field? If yes, remove the duplicate.

LESSON MODE — choose the one that matches the teacher's goal:
  first_exposure    — learner meets this concept for the first time;
                      sequence: orient → understand → model → practice → summary
  consolidation     — learner knows the concept but needs depth or connection;
                      reduce explanation, increase practice variety and difficulty
  repair            — learner has a specific misconception;
                      prioritise pitfall-alert and targeted explanation before practice
  retrieval         — spaced recall session with no new teaching;
                      use only practice and quiz components; no explanation or worked example
  transfer          — applying understanding to an unfamiliar context;
                      use challenge components and simulation if available

RESOURCE TYPE — choose the format that matches what the teacher needs:
  lesson              — full instructional lesson; all phases available
  mini_booklet        — compact lesson; reduce scaffolding, tighter component budget
  quiz                — assessment-first; primarily practice and quiz components,
                        minimal or no explanation sections
  retrieval_practice  — spaced recall only; no new teaching, cold and transfer questions
  worked_example_set  — model-heavy; multiple worked examples with light practice

OUTPUT RULES:
- Only use component slugs from the AVAILABLE COMPONENTS list above. Never invent slugs.
- metadata: version "3.0", title, subject (from teacher subject)
- lesson: lesson_mode and resource_type from the options above
- applied_lenses: min 1 lens with lens_id and effects (non-empty strings)
- voice: register (simple|balanced|formal etc), optional tone
- anchor: reuse_scope string
- sections: min 1, each with section_id, title, role, visual_required bool,
  components min 1 with component slug and content_intent
- question_plan: min 1 items with question_id, section_id,
  temperature warm|medium|cold|transfer, prompt, expected_answer, diagram_required
- visual_strategy: visuals list (section_id, strategy, optional density)
- answer_key: style string (e.g. concise_steps, answers_only)
- teacher_materials, prior_knowledge lists allowed
Use sensible IDs like orient, model, practice, summary for sections when appropriate."""
```

If `_planner_index_block()` is already in place, the historical variant used `{planner_block}` and omitted `{budget_rules}{section_rules}` — same protocol and OUTPUT RULES body as above.

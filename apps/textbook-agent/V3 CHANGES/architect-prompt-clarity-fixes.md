# Architect Prompt Clarity Fixes
## Six misunderstandings identified and resolved

**Files touched:**
- `backend/src/generation/v3_studio/prompts.py` — `REASONING_SCAFFOLD` constant and OUTPUT RULES in `build_architect_system_prompt()`
- `backend/src/generation/v3_lenses/loader.py` — `format_lenses_for_prompt()`

---

## Fix 1 — Step 5: align role taxonomy with actual phase names and correct the example

**Problem:** Step 5a lists roles as `orient / understand / model / practice / alert / visual / simulate`.
The AVAILABLE COMPONENTS block uses: `Orient / Build Knowledge / Model / Practice and Check / Address Mistakes / Visualize / Interact`.
Four of seven don't match. The example then points `explanation-block` at "Phase 2 — Understand" — a phase that doesn't exist by that name, and the wrong phase anyway since `explanation-block` lives in Phase 1 — Orient.

**Fix:** Replace Step 5 in `REASONING_SCAFFOLD`. Change the role vocabulary to match the contract phase names exactly, add the clarifying note about phases being planner groupings, and correct the example.

```python
STEP 5 — COMPONENT MAPPING (phase-first)
  Phase names in the AVAILABLE COMPONENTS list are planner groupings from
  the Lectio contract — use them to locate components in the palette.
  For instructional intent, use each component's role and cognitive_job,
  not the phase name alone.

  Map each sequence move to one component slug.
  Follow this order for every move:
    a. Find the phase that covers this kind of move.
       Use the exact phase names shown in AVAILABLE COMPONENTS:
         Phase 1 — Orient            (framing, opening, context-setting)
         Phase 2 — Build Knowledge   (defining, comparing, anchoring terms)
         Phase 3 — Model             (worked examples, procedures)
         Phase 4 — Practice and Check (questions, retrieval, reflection)
         Phase 5 — Address Mistakes  (pitfall alerts, misconception correction)
         Phase 6 — Visualize         (diagrams, timelines, comparisons)
         Phase 7 — Interact          (simulations)
    b. Choose the right component from that phase for this learner and context.
       Read its role and cognitive_job to confirm it matches your intent —
       the phase is the palette; role/cognitive_job is the selection signal.
    c. Check section_field — no two components with the same field in one section.
  (Answer as: move → phase → slug [field], one line each.)

  Examples:
    "Open by building the learner's mental model of osmosis"
    → Phase 1 — Orient → explanation-block [explanation]
    (explanation-block sits in Orient in this contract; its cognitive_job
     is 'Build understanding' — the phase groups it here for UI/manifest,
     not to say it is motivational-only.)

    "Define osmosis precisely before the worked example"
    → Phase 2 — Build Knowledge → definition-card [definition]

    "Show a worked problem before independent practice"
    → Phase 3 — Model → worked-example-card [worked_example]

    "Let students apply the concept with scaffolded problems"
    → Phase 4 — Practice and Check → practice-stack [practice]
```

---

## Fix 2 — `format_lenses_for_prompt()`: emit `conflicts_with`

**Problem:** Step 2.5 says "Check `conflicts_with` — do not apply lenses that conflict."
`format_lenses_for_prompt()` never emits `conflicts_with` data so the architect is told to check something it cannot see. `LensSchema.conflicts_with: list[str]` is populated — e.g. `transfer` conflicts with `first_exposure` and `repair`.

**Fix:** In `backend/src/generation/v3_lenses/loader.py`, update `format_lenses_for_prompt()`:

```python
def format_lenses_for_prompt() -> str:
    lines = ["Pedagogical lenses — apply those that fit the teacher's signals:"]
    for lens in sorted(get_all_lenses(), key=lambda item: item.id):
        lines.append(f"\n  {lens.id} ({lens.label}) — {lens.applies_when.strip()}")
        lines.append("  Principles:")
        for principle in lens.reasoning_principles[:3]:
            lines.append(f"    - {principle}")
        if lens.avoid:
            lines.append(f"  Avoid: {', '.join(lens.avoid[:3])}")
        if lens.conflicts_with:                                          # ← add this block
            lines.append(f"  Conflicts with: {', '.join(lens.conflicts_with)}")
    return "\n".join(lines)
```

That is the complete change to `loader.py`. One block, four lines.

---

## Fix 3 — Step 4: close the loop back to resource spec constraints

**Problem:** Step 3 locks forbidden components from the resource spec. Step 4 says "write the teaching sequence" with no reminder to stay within those constraints. An architect can plan an explanation move for a worksheet and only discover the conflict when it reaches Step 5 — or not at all.

**Fix:** Add one sentence at the end of Step 4 in `REASONING_SCAFFOLD`:

```python
STEP 4 — TEACHING SEQUENCE
  Given the lesson_mode, learner_level, and the lens effects from Step 2.5,
  write the teaching sequence as an ordered list of 4–6 moves.
  Each move is one verb phrase: "Orient the learner to...", "Explain how to...",
  "Model with...", "Practice...".
  Apply lens effects here: if a lens says "lead with a worked example", put Model
  before Understand. If a lens says "define terms first", put Build Knowledge before
  Explain. The sequence should reflect how a good teacher would actually order this.
  Each move must only use components that are not forbidden by the resource spec
  (Step 3). If a move would require a forbidden component, replace or remove it now.
  (Answer as a numbered list.)
```

---

## Fix 4 — OUTPUT RULES: clarify `visual_required` and `visual_strategy` consistency

**Problem:** Step 6 decides yes/no per section. OUTPUT RULES mention both `visual_required` on sections and `visual_strategy` as a separate field. The architect can set `visual_required: false` on a section but still add it to `visual_strategy`, or set the flag but forget the strategy entry. The two must be consistent and the prompt never says so.

**Fix:** Update the `visual_strategy` and `sections` lines in OUTPUT RULES inside `build_architect_system_prompt()`:

```
- sections: each with section_id, title, role, visual_required bool,
  components with slug and content_intent.
  Set visual_required = true only for sections where Step 6 confirmed a visual
  is needed. Every section in visual_strategy must have visual_required = true,
  and every section with visual_required = true must appear in visual_strategy.
  content_intent must be specific enough that a writer can act on it without
  asking questions.
  Bad:  "explain photosynthesis"
  Good: "explain light-dependent reactions; contrast what happens with and
         without sunlight; use the chloroplast membrane as the anchor structure
         throughout"
- visual_strategy: one entry per section where visual_required = true.
  Each item: section_id, strategy (what the visual must show — be specific),
  optional density (low / medium / high).
  Do not add visual_strategy entries for sections with visual_required = false.
```

---

## Fix 5 — OUTPUT RULES: correct the `question_plan` minimum for spec-constrained resources

**Problem:** `question_plan: min 1 items` is stated unconditionally, but some resource types (quick_explainer, mini_booklet) may not require questions. The Pydantic model enforces min 1 at the schema level, but the prompt should acknowledge when the resource spec overrides this expectation so the architect doesn't pad meaningless questions.

**Fix:** Update the `question_plan` line in OUTPUT RULES:

```
- question_plan: one item per planned question. Temperature must match
  lesson_mode guidance from Step 7. If the resource spec in your context
  window specifies no questions or a different format, follow the spec —
  include at least one minimal question only if the schema requires it.
  Each item: question_id, section_id, temperature, prompt, expected_answer,
  diagram_required.
```

---

## The complete updated `REASONING_SCAFFOLD`

This is the full replacement for the `REASONING_SCAFFOLD` constant. Apply it as a single block — do not merge line by line.

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
  Check "Conflicts with" — do not apply lenses listed as conflicting with each other.
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
  (Answer as: purpose / forbidden components / required sections list.)

  This step is a gate. If you plan a component that the spec forbids,
  the output is wrong. Check forbidden_components before proceeding.
  If no spec is shown for the resource type, proceed using lesson_mode
  constraints and your judgment.

STEP 4 — TEACHING SEQUENCE
  Given the lesson_mode, learner_level, and the lens effects from Step 2.5,
  write the teaching sequence as an ordered list of 4–6 moves.
  Each move is one verb phrase: "Orient the learner to...", "Explain how to...",
  "Model with...", "Practice...".
  Apply lens effects here: if a lens says "lead with a worked example", put Model
  before Build Knowledge. If a lens says "define terms first", put Build Knowledge
  before the explanation move.
  Each move must only use components that are not forbidden by the resource spec
  (Step 3). If a move would require a forbidden component, replace or remove it now.
  (Answer as a numbered list.)

STEP 5 — COMPONENT MAPPING (phase-first)
  Phase names in the AVAILABLE COMPONENTS list are planner groupings from
  the Lectio contract — use them to locate components in the palette.
  For instructional intent, use each component's role and cognitive_job,
  not the phase name alone.

  Map each sequence move to one component slug.
  Follow this order for every move:
    a. Find the phase that covers this kind of move.
       Use the exact phase names shown in AVAILABLE COMPONENTS:
         Phase 1 — Orient            (framing, opening, context-setting, model-building)
         Phase 2 — Build Knowledge   (defining, comparing, anchoring key terms)
         Phase 3 — Model             (worked examples, step-by-step procedures)
         Phase 4 — Practice and Check (questions, retrieval, reflection, write-in)
         Phase 5 — Address Mistakes  (pitfall alerts, misconception correction)
         Phase 6 — Visualize         (diagrams, timelines, comparison grids)
         Phase 7 — Interact          (simulations)
    b. Choose the right component from that phase for this learner and context.
       Read its role and cognitive_job to confirm it matches your intent —
       the phase is the palette; role/cognitive_job is the selection signal.
    c. Check section_field — no two components with the same field in one section.
  (Answer as: move → phase → slug [field], one line each.)

  Examples:
    "Open by building the learner's mental model of osmosis"
    → Phase 1 — Orient → explanation-block [explanation]
    (explanation-block sits in Orient in this contract; its cognitive_job
     is 'Build understanding' — the phase groups it here for UI/manifest,
     not to say it is motivational-only.)

    "Define osmosis precisely before the worked example"
    → Phase 2 — Build Knowledge → definition-card [definition]

    "Show a worked problem before independent practice"
    → Phase 3 — Model → worked-example-card [worked_example]

    "Let students apply the concept with scaffolded problems"
    → Phase 4 — Practice and Check → practice-stack [practice]

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

## The complete updated OUTPUT RULES block in `build_architect_system_prompt()`

Replace the entire OUTPUT RULES section at the end of the return string:

```python
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
  Set visual_required = true only for sections where Step 6 confirmed a visual
  is needed. Every section in visual_strategy must have visual_required = true,
  and every section with visual_required = true must appear in visual_strategy.
  content_intent must be specific enough that a writer can act on it without
  asking questions.
  Bad:  "explain photosynthesis"
  Good: "explain light-dependent reactions; contrast what happens with and
         without sunlight; use the chloroplast membrane as the anchor structure
         throughout"
- question_plan: one item per planned question. Temperature must match lesson_mode
  guidance from Step 7. If the resource spec specifies no questions or a different
  format, follow the spec — include at least one minimal question only if the
  schema requires it.
  Each item: question_id, section_id, temperature, prompt, expected_answer,
  diagram_required.
- visual_strategy: one entry per section where visual_required = true.
  Each item: section_id, strategy (what the visual must show — be specific),
  optional density (low / medium / high).
  Do not add visual_strategy entries for sections with visual_required = false.
- answer_key: style — answers_only | brief_explanations | full_working
- repair_focus: required when lesson_mode = repair.
  fault_line: what specifically went wrong (one sentence).
  what_not_to_teach: list of things to exclude from this lesson.
- teacher_materials and prior_knowledge lists are allowed and encouraged.
Use short, clear section IDs: orient, understand, model, practice, alert, summary."""
```

---

## Verification

After applying both file changes:

```bash
uv run python -c "
from generation.v3_studio.prompts import REASONING_SCAFFOLD, build_architect_system_prompt
from generation.v3_lenses.loader import format_lenses_for_prompt

# Fix 1: phase names present and correct
assert 'Phase 1 — Orient' in REASONING_SCAFFOLD
assert 'Phase 2 — Build Knowledge' in REASONING_SCAFFOLD
assert 'Phase 5 — Address Mistakes' in REASONING_SCAFFOLD
assert 'orient / understand / model' not in REASONING_SCAFFOLD, 'Old role taxonomy still present'

# Fix 1: example corrected
assert 'Phase 2 — Understand' not in REASONING_SCAFFOLD, 'Wrong phase name in example'
assert 'Phase 1 — Orient → explanation-block' in REASONING_SCAFFOLD

# Fix 2: conflicts_with visible
lenses = format_lenses_for_prompt()
assert 'Conflicts with:' in lenses, 'conflicts_with not emitted'

# Fix 3: resource spec constraint in Step 4
assert 'forbidden by the resource spec' in REASONING_SCAFFOLD

# Fix 4: visual consistency rule
prompt = build_architect_system_prompt()
assert 'Every section in visual_strategy must have visual_required = true' in prompt

# Fix 5: question_plan spec override
assert 'follow the spec' in prompt

print('All clarity fixes verified OK')
"
```

---

## Summary of what each fix addresses

| Fix | File | Lines changed | Risk eliminated |
|---|---|---|---|
| 1 | `prompts.py` — `REASONING_SCAFFOLD` | Step 5 rewritten | Architect maps moves to wrong phase, picks wrong component because taxonomy words didn't match |
| 2 | `loader.py` — `format_lenses_for_prompt()` | +4 lines | Architect told to check `conflicts_with` but couldn't see the data |
| 3 | `prompts.py` — `REASONING_SCAFFOLD` | 1 sentence added to Step 4 | Resource spec forbidden components not applied during sequence planning |
| 4 | `prompts.py` — OUTPUT RULES | `sections` and `visual_strategy` entries rewritten | `visual_required` and `visual_strategy` inconsistent, one set the other missing |
| 5 | `prompts.py` — OUTPUT RULES | `question_plan` line rewritten | Meaningless padding questions forced for resource types that don't need them |

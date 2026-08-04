# v3 Patchwork — Form Expansion + Directed Reasoning + Timeout Fix

## Overview

Three fixes in one pass:
1. Expand the input form to capture structured data the LLM currently guesses
2. Add a reasoning scaffold to the architect system prompt to bound thinking
3. Increase the architect timeout to 300s

---

## Fix 1 — Expand the input form

### What to add

The LLM currently infers lesson_mode, learner_level, support_needs, and
prior_knowledge from free text. These vary because inference is inconsistent.
A form captures them in one click with zero ambiguity.

**Add to `V3InputForm` in `backend/src/generation/v3_studio/dtos.py`:**

```python
class V3InputForm(BaseModel):
    model_config = {"extra": "forbid"}

    year_group: str
    subject: str
    duration_minutes: int = Field(ge=15, le=180)

    # New structured fields
    lesson_mode: Literal[
        "first_exposure",
        "consolidation",
        "repair",
        "retrieval",
        "transfer"
    ] = "first_exposure"

    learner_level: Literal[
        "below_average",
        "average",
        "above_average",
        "mixed"
    ] = "average"

    support_needs: list[Literal["eal", "high_load", "advanced"]] = Field(
        default_factory=list
    )

    prior_knowledge: str = ""   # "what have they already covered?"

    free_text: str              # topic + concept description only
```

**Add to `V3InputForm` in `frontend/src/lib/types/v3.ts`:**

```typescript
export interface V3InputForm {
    year_group: string;
    subject: string;
    duration_minutes: number;
    lesson_mode: 'first_exposure' | 'consolidation' | 'repair' | 'retrieval' | 'transfer';
    learner_level: 'below_average' | 'average' | 'above_average' | 'mixed';
    support_needs: ('eal' | 'high_load' | 'advanced')[];
    prior_knowledge: string;
    free_text: string;
}
```

### Updated V3InputSurface.svelte

Replace the current three-field form with this expanded form.
Keep the layout clean — new fields go between duration and free_text:

```svelte
<script lang="ts">
    // Add new state
    let lesson_mode = $state('first_exposure');
    let learner_level = $state('average');
    let support_needs = $state<string[]>([]);
    let prior_knowledge = $state('');

    const LESSON_MODES = [
        { value: 'first_exposure', label: 'First time teaching this' },
        { value: 'consolidation',  label: 'They know it — need practice' },
        { value: 'repair',         label: 'Something went wrong — fix it' },
        { value: 'retrieval',      label: 'Quick recall from earlier' },
        { value: 'transfer',       label: 'Apply it in a new context' },
    ];

    const LEARNER_LEVELS = [
        { value: 'below_average', label: 'Below expected level' },
        { value: 'average',       label: 'At expected level' },
        { value: 'above_average', label: 'Above expected level' },
        { value: 'mixed',         label: 'Mixed ability' },
    ];

    // support_needs is a multi-select checkbox group
    // eal, high_load (ADHD/dyslexia), advanced

    function toggleSupport(need: string) {
        if (support_needs.includes(need)) {
            support_needs = support_needs.filter(n => n !== need);
        } else {
            support_needs = [...support_needs, need];
        }
    }

    // canSubmit: year_group, subject, free_text.length > 10
    // (prior_knowledge is optional, lesson_mode/learner_level have defaults)
</script>

<!-- In the form, add after duration select: -->

<label class="grid gap-1 text-sm font-medium">
    <span>What is this lesson for?</span>
    <select bind:value={lesson_mode}>
        {#each LESSON_MODES as m}
            <option value={m.value}>{m.label}</option>
        {/each}
    </select>
</label>

<label class="grid gap-1 text-sm font-medium">
    <span>Learner level</span>
    <select bind:value={learner_level}>
        {#each LEARNER_LEVELS as l}
            <option value={l.value}>{l.label}</option>
        {/each}
    </select>
</label>

<fieldset class="grid gap-1">
    <legend class="text-sm font-medium">Support needs (tick all that apply)</legend>
    <div class="flex gap-4 text-sm">
        <label class="flex items-center gap-2">
            <input type="checkbox" checked={support_needs.includes('eal')}
                   onchange={() => toggleSupport('eal')} />
            EAL learners
        </label>
        <label class="flex items-center gap-2">
            <input type="checkbox" checked={support_needs.includes('high_load')}
                   onchange={() => toggleSupport('high_load')} />
            ADHD / dyslexia
        </label>
        <label class="flex items-center gap-2">
            <input type="checkbox" checked={support_needs.includes('advanced')}
                   onchange={() => toggleSupport('advanced')} />
            Advanced learners
        </label>
    </div>
</fieldset>

<label class="grid gap-1 text-sm font-medium">
    <span>What have they already covered? <span class="text-muted-foreground">(optional)</span></span>
    <input type="text"
           bind:value={prior_knowledge}
           placeholder="e.g. basic rectangle area, multiplication to 12×12" />
</label>

<label class="grid gap-1 text-sm font-medium">
    <span>Topic and intent</span>
    <textarea bind:value={free_text} rows={4}
              placeholder="Describe the concept and what you want learners to do.
Example: Compound area using L-shapes — want them to be able to split and calculate independently." />
</label>
```

### What the LLM no longer needs to infer

With this form:
- lesson_mode → comes from form directly
- learner_level → comes from form directly
- support_needs → comes from form directly
- prior_knowledge → comes from form directly
- topic → extracted from free_text (simple, unambiguous)

**Clarification is now almost never needed.** The only remaining gap is
pedagogical intent ambiguity in the free_text — and that's resolved by
the signal confirmation step, not a clarification call.

### Skip clarification when form data is complete

In `agents.py`, the clarification call should be skipped when the form
provides lesson_mode, learner_level, and support_needs:

```python
# In router.py post_signals or in the frontend logic:
# If form.lesson_mode is set and form.learner_level is set,
# skip clarification entirely and go straight to blueprint.
```

Or more precisely, update the `CLARIFY_SYSTEM` prompt to explicitly state:
"Do not ask about lesson mode, learner level, support needs, or prior
knowledge — these are already provided in the form data."

---

## Fix 2 — Directed reasoning scaffold in architect prompt

### The principle

Without a scaffold, Opus explores freely before narrowing. This produces
good blueprints but takes 200–300s and is unpredictable.

A reasoning scaffold gives Opus explicit questions to answer in sequence.
The model thinks freely within each step but cannot wander between them.
Thinking time drops to 60–120s. Output is more consistent.

This is not a chain-of-thought that appears in the output. It is a
reasoning directive that shapes the *thinking process*, not the response
format. The output is still the `ProductionBlueprint` JSON.

### Update `build_architect_system_prompt()` in `prompts.py`

Add the scaffold block before the Rules section:

```python
REASONING_SCAFFOLD = """
REASONING STEPS — work through these in order before producing the blueprint.
Keep each answer short. The goal is to lock in decisions before building.

STEP 1 — LEARNER
  Who is this class? What is their level and what are their main barriers?
  What does their support profile mean for content density and visual load?
  (Answer in 2 sentences.)

STEP 2 — CONCEPT
  What is the core concept in one sentence?
  What is the single hardest step for this learner to understand?
  What misconception most commonly arises here?
  (Answer in 3 sentences.)

STEP 3 — SEQUENCE
  Given the lesson_mode and learner_level, write the teaching sequence
  as an ordered list of 4–6 moves.
  Each move should be one verb phrase: "Orient the learner to...",
  "Explain how to...", "Model with...", "Practice...".
  (Answer as a numbered list.)

STEP 4 — COMPONENTS
  Map each sequence move to one or two component slugs from the manifest.
  Check section_field — no two components with the same field in one section.
  (Answer as: move → slug [field].)

STEP 5 — VISUALS
  For each section, answer yes or no: does this concept require visual
  support here? Spatial and procedural steps need visuals.
  Definitions and warnings usually do not.
  (Answer as: section → yes/no, one word reason.)

STEP 6 — QUESTIONS
  What is the right difficulty progression given this learner?
  Write one sentence per question: difficulty, what cognitive move it tests,
  whether it needs a diagram.
  (Answer as: Q1 warm — ..., Q2 medium — ... etc.)

Now produce the ProductionBlueprint JSON exactly matching the schema.
Do not include the reasoning steps in the JSON output.
"""
```

Inject it into the system prompt:

```python
def build_architect_system_prompt() -> str:
    ...
    return f"""You are a lesson architect. Output ONLY a valid ProductionBlueprint JSON.

{_manifest_block()}

CONSTRAINT: Each section_field may appear at most once per section.
{budget_rules}{section_rules}

{_lens_block()}

{REASONING_SCAFFOLD}

OUTPUT RULES:
- Only use slugs from the manifest above.
- metadata: version "3.0", title, subject
- lesson: lesson_mode from form (already decided — do not change it)
- applied_lenses: min 1, lens_id from the lens list, effects non-empty
- voice: register simple|balanced|formal
- sections: min 1, visual_required bool, components with content_intent
- question_plan: min 1, expected_answer required on every question
- visual_strategy: entry for every section where visual_required=true
- answer_key: style e.g. concise_steps
"""
```

### What changes in practice

**Before scaffold:** Opus explores lesson design broadly, considers
alternatives, backtracks, then narrows to a blueprint. 200–300s.

**After scaffold:** Opus answers 6 bounded questions in sequence, each
building on the last. The blueprint writes itself from the answers.
60–120s. Output is more consistent because the reasoning path is fixed.

**Traceability:** Each step is short enough to appear in a debug log if
needed. If a blueprint has a bad sequence, you can see which step went
wrong. This is the "flexible but traceable" property you asked for.

---

## Fix 3 — Increase architect timeout

**File:** `backend/src/v3_execution/config/timeouts.py`

```python
# Before
"lesson_architect": int(os.getenv("V3_TIMEOUT_ARCHITECT_SECONDS", "180")),

# After
"lesson_architect": int(os.getenv("V3_TIMEOUT_ARCHITECT_SECONDS", "300")),
```

**Railway env var** — set `V3_TIMEOUT_ARCHITECT_SECONDS=300` in Railway.
The env var takes precedence so no redeploy needed for this change alone.

---

## What this eliminates from the LLM pipeline

Before this patch:
```
Form (3 fields) → Signal Extractor → Clarification (1-2 questions) → Architect
```

After this patch:
```
Form (8 fields) → Signal Extractor (confirms topic only) → Architect
```

Clarification is now an exceptional path, not the default. Signal extractor
becomes a lightweight topic confirmation, not a full inference task. The
architect receives complete structured context and uses the reasoning
scaffold to produce a consistent blueprint in under 120s.

---

## Implementation order

```
1. dtos.py — add new fields to V3InputForm
2. types/v3.ts — add new fields to V3InputForm TypeScript type
3. V3InputSurface.svelte — add form controls for new fields
4. CLARIFY_SYSTEM prompt — add "do not ask about lesson_mode,
   learner_level, support_needs, prior_knowledge"
5. prompts.py — add REASONING_SCAFFOLD to build_architect_system_prompt()
6. timeouts.py — increase default to 300s
7. Railway — set V3_TIMEOUT_ARCHITECT_SECONDS=300
```

Steps 1–3 and 5–7 are independent. Step 4 depends on Step 1.

---

## Verification

```
□ Form has lesson_mode, learner_level, support_needs, prior_knowledge fields
□ Submitting with first_exposure + below_average + eal produces blueprint
  with first_exposure lens and eal lens applied — without clarification step
□ Blueprint generation completes within 150s for a standard brief
□ No timeout error on Railway with V3_TIMEOUT_ARCHITECT_SECONDS=300
□ CLARIFY_SYSTEM does not ask about fields already in the form
□ Blueprint lesson_mode matches the form value — not re-inferred by LLM
```

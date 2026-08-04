# v3 Patchwork — Comprehensive Form Redesign

## Philosophy

Borrow the best of v2 (subtopic resolution, class profile richness)
while keeping v3's minimal approach. Every field that has a finite answer
is a form control. The LLM gets structured data, not inference tasks.
Clarification becomes exceptional, not the default path.

Five steps instead of v2's ten. No depth picker, no build mode, no
resource type picker in the form.

---

## Duration field — gradated

Replace the 4-option select with 5-minute increments from 15 to 90.
Use a select with all options, with common breakpoints visually grouped:

```svelte
const DURATIONS = [
    { label: '15 min', value: 15 },
    { label: '20 min', value: 20 },
    { label: '25 min', value: 25 },
    { label: '30 min', value: 30 },   // --- short lesson ---
    { label: '35 min', value: 35 },
    { label: '40 min', value: 40 },
    { label: '45 min', value: 45 },
    { label: '50 min', value: 50 },   // --- standard lesson ---
    { label: '55 min', value: 55 },
    { label: '60 min', value: 60 },
    { label: '75 min', value: 75 },   // --- extended lesson ---
    { label: '90 min', value: 90 },
]
```

Default to 50 min.

---

## Updated V3InputForm

### Backend: `backend/src/generation/v3_studio/dtos.py`

```python
from typing import Literal
from pydantic import BaseModel, Field


class V3InputForm(BaseModel):
    model_config = {"extra": "forbid"}

    # Step 1 — Basics
    grade_level: str                          # e.g. "Grade 9"
    subject: str
    duration_minutes: int = Field(ge=15, le=90)

    # Step 2 — Concept
    topic: str                                # raw topic text
    subtopics: list[str] = Field(default_factory=list)  # resolved subtopics
    prior_knowledge: str = ""                 # what they've already covered

    # Step 3 — Lesson shape
    lesson_mode: Literal[
        "first_exposure",
        "consolidation",
        "repair",
        "retrieval",
        "transfer",
        "other"
    ] = "first_exposure"
    lesson_mode_other: str = ""              # filled when lesson_mode = "other"

    intended_outcome: Literal[
        "understand",
        "practise",
        "review",
        "assess",
        "other"
    ] = "understand"
    intended_outcome_other: str = ""         # filled when intended_outcome = "other"

    # Step 4 — Class profile
    learner_level: Literal[
        "below_grade",
        "on_grade",
        "above_grade",
        "mixed"
    ] = "on_grade"

    reading_level: Literal[
        "below_grade",
        "on_grade",
        "above_grade",
        "mixed"
    ] = "on_grade"

    language_support: Literal[
        "none",
        "some_ell",
        "many_ell"
    ] = "none"

    prior_knowledge_level: Literal[
        "new_topic",
        "some_background",
        "reviewing"
    ] = "new_topic"

    support_needs: list[str] = Field(default_factory=list)
    # values: "eal", "high_load", "advanced", or free-text from Other

    learning_preferences: list[Literal[
        "visual",
        "step_by_step",
        "discussion",
        "hands_on",
        "challenge"
    ]] = Field(default_factory=list)

    # Step 5 — Optional intent
    free_text: str = ""                      # anything not captured above
```

### Frontend: `frontend/src/lib/types/v3.ts`

```typescript
export interface V3InputForm {
    // Step 1
    grade_level: string;
    subject: string;
    duration_minutes: number;

    // Step 2
    topic: string;
    subtopics: string[];
    prior_knowledge: string;

    // Step 3
    lesson_mode: 'first_exposure' | 'consolidation' | 'repair' |
                 'retrieval' | 'transfer' | 'other';
    lesson_mode_other: string;
    intended_outcome: 'understand' | 'practise' | 'review' | 'assess' | 'other';
    intended_outcome_other: string;

    // Step 4
    learner_level: 'below_grade' | 'on_grade' | 'above_grade' | 'mixed';
    reading_level: 'below_grade' | 'on_grade' | 'above_grade' | 'mixed';
    language_support: 'none' | 'some_ell' | 'many_ell';
    prior_knowledge_level: 'new_topic' | 'some_background' | 'reviewing';
    support_needs: string[];
    learning_preferences: string[];

    // Step 5
    free_text: string;
}
```

---

## V3InputSurface.svelte — full redesign

Replace the current single-page form with a 5-step vertical wizard.
Each step is a clearly labelled section. All visible at once on desktop
(no hidden steps) — just a clean vertical stack the teacher scrolls through.

```svelte
<script lang="ts">
    // --- Step 1 state ---
    let grade_level = $state('');
    let subject = $state('');
    let duration_minutes = $state(50);

    // --- Step 2 state ---
    let topic = $state('');
    let subtopics = $state<string[]>([]);
    let subtopic_candidates = $state<SubtopicCandidate[]>([]);
    let prior_knowledge = $state('');
    let resolving_topic = $state(false);

    // --- Step 3 state ---
    let lesson_mode = $state('first_exposure');
    let lesson_mode_other = $state('');
    let intended_outcome = $state('understand');
    let intended_outcome_other = $state('');

    // --- Step 4 state ---
    let learner_level = $state('on_grade');
    let reading_level = $state('on_grade');
    let language_support = $state('none');
    let prior_knowledge_level = $state('new_topic');
    let support_needs = $state<string[]>([]);
    let support_other = $state('');
    let learning_preferences = $state<string[]>([]);

    // --- Step 5 state ---
    let free_text = $state('');

    const GRADE_LEVELS = [
        'Kindergarten',
        'Grade 1', 'Grade 2', 'Grade 3', 'Grade 4', 'Grade 5',
        'Grade 6', 'Grade 7', 'Grade 8', 'Grade 9',
        'Grade 10', 'Grade 11', 'Grade 12',
    ];

    const SUBJECTS = [
        'Mathematics', 'English Language Arts', 'Science', 'Biology',
        'Chemistry', 'Physics', 'History', 'Geography', 'Economics',
        'Computer Science', 'Art', 'Music', 'Physical Education', 'Other'
    ];

    const DURATIONS = [
        15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 75, 90
    ].map(v => ({ label: `${v} min`, value: v }));

    const LESSON_MODES = [
        { value: 'first_exposure', label: 'First time teaching this' },
        { value: 'consolidation',  label: 'They know it — need more practice' },
        { value: 'repair',         label: 'Something went wrong — fix it' },
        { value: 'retrieval',      label: 'Quick recall from earlier' },
        { value: 'transfer',       label: 'Apply it in a new context' },
        { value: 'other',          label: 'Other (describe below)' },
    ];

    const OUTCOMES = [
        { value: 'understand', label: 'Understand the concept' },
        { value: 'practise',   label: 'Practise and apply' },
        { value: 'review',     label: 'Review and consolidate' },
        { value: 'assess',     label: 'Check understanding' },
        { value: 'other',      label: 'Other (describe below)' },
    ];

    const LEARNER_LEVELS = [
        { value: 'below_grade', label: 'Below grade level' },
        { value: 'on_grade',    label: 'At grade level' },
        { value: 'above_grade', label: 'Above grade level' },
        { value: 'mixed',       label: 'Mixed ability' },
    ];

    const READING_LEVELS = [
        { value: 'below_grade', label: 'Below grade reading level' },
        { value: 'on_grade',    label: 'At grade reading level' },
        { value: 'above_grade', label: 'Above grade reading level' },
        { value: 'mixed',       label: 'Mixed' },
    ];

    const LANGUAGE_OPTIONS = [
        { value: 'none',     label: 'English only / no ELL needs' },
        { value: 'some_ell', label: 'Some ELL learners' },
        { value: 'many_ell', label: 'Mostly ELL learners' },
    ];

    const PRIOR_KNOWLEDGE_OPTIONS = [
        { value: 'new_topic',       label: 'Brand new — no prior exposure' },
        { value: 'some_background', label: 'Some background knowledge' },
        { value: 'reviewing',       label: 'Reviewing something taught before' },
    ];

    const SUPPORT_OPTIONS = [
        { value: 'visuals',            label: 'Visual learners' },
        { value: 'step_by_step',       label: 'Need step-by-step scaffolding' },
        { value: 'vocabulary_support', label: 'Vocabulary support needed' },
        { value: 'worked_examples',    label: 'Benefit from worked examples' },
        { value: 'simpler_reading',    label: 'Simplified reading level' },
        { value: 'challenge',          label: 'Include challenge questions' },
    ];

    const LEARNING_PREFERENCES = [
        { value: 'visual',       label: 'Visual' },
        { value: 'step_by_step', label: 'Step-by-step' },
        { value: 'discussion',   label: 'Discussion' },
        { value: 'hands_on',     label: 'Hands-on' },
        { value: 'challenge',    label: 'Challenge' },
    ];

    // Topic resolution — reuses existing v2 backend endpoint
    async function resolveTopic() {
        if (!topic.trim() || !grade_level) return;
        resolving_topic = true;
        try {
            const res = await fetch('/api/v1/planning/brief/topic', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ...authHeaders() },
                body: JSON.stringify({
                    raw_topic: topic,
                    grade_level: toGradeLevelEnum(grade_level),
                    grade_band: toGradeBand(grade_level),
                })
            });
            const data = await res.json();
            subtopic_candidates = data.candidate_subtopics ?? [];
            subtopics = [];
        } finally {
            resolving_topic = false;
        }
    }

    function toggleSubtopic(id: string, title: string) {
        const already = subtopics.includes(title);
        if (already) {
            subtopics = subtopics.filter(s => s !== title);
        } else if (subtopics.length < 3) {
            subtopics = [...subtopics, title];
        }
    }

    function toggleSupport(val: string) {
        support_needs = support_needs.includes(val)
            ? support_needs.filter(s => s !== val)
            : [...support_needs, val];
    }

    function togglePreference(val: string) {
        learning_preferences = learning_preferences.includes(val)
            ? learning_preferences.filter(p => p !== val)
            : [...learning_preferences, val];
    }

    function addSupportOther() {
        if (!support_other.trim()) return;
        if (!support_needs.includes(support_other.trim())) {
            support_needs = [...support_needs, support_other.trim()];
        }
        support_other = '';
    }

    const canSubmit = $derived(
        grade_level !== '' &&
        subject !== '' &&
        topic.trim().length > 2
    );

    function buildForm(): V3InputForm {
        const all_supports = [
            ...support_needs,
        ];
        return {
            grade_level,
            subject,
            duration_minutes: Number(duration_minutes),
            topic: topic.trim(),
            subtopics,
            prior_knowledge: prior_knowledge.trim(),
            lesson_mode: lesson_mode as any,
            lesson_mode_other: lesson_mode_other.trim(),
            intended_outcome: intended_outcome as any,
            intended_outcome_other: intended_outcome_other.trim(),
            learner_level: learner_level as any,
            reading_level: reading_level as any,
            language_support: language_support as any,
            prior_knowledge_level: prior_knowledge_level as any,
            support_needs: all_supports,
            learning_preferences: learning_preferences as any,
            free_text: free_text.trim(),
        };
    }
</script>

<div class="mx-auto max-w-xl space-y-10 px-4 py-10">
    <header class="text-center">
        <h1 class="text-3xl font-semibold">What do you want to teach?</h1>
    </header>

    <!-- STEP 1 — BASICS -->
    <section class="space-y-4">
        <h2 class="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            The basics
        </h2>
        <div class="grid gap-3 sm:grid-cols-3">
            <label class="grid gap-1 text-sm font-medium">
                <span>Grade level</span>
                <select bind:value={grade_level}>
                    <option value="">Choose…</option>
                    {#each GRADE_LEVELS as g}
                        <option value={g}>{g}</option>
                    {/each}
                </select>
            </label>
            <label class="grid gap-1 text-sm font-medium">
                <span>Subject</span>
                <select bind:value={subject}>
                    <option value="">Choose…</option>
                    {#each SUBJECTS as s}
                        <option value={s}>{s}</option>
                    {/each}
                </select>
            </label>
            <label class="grid gap-1 text-sm font-medium">
                <span>Duration</span>
                <select bind:value={duration_minutes}>
                    {#each DURATIONS as d}
                        <option value={d.value}>{d.label}</option>
                    {/each}
                </select>
            </label>
        </div>
    </section>

    <!-- STEP 2 — CONCEPT -->
    <section class="space-y-4">
        <h2 class="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            The concept
        </h2>

        <label class="grid gap-1 text-sm font-medium">
            <span>Topic</span>
            <div class="flex gap-2">
                <input
                    class="flex-1 rounded-md border border-input bg-background px-3 py-2"
                    bind:value={topic}
                    placeholder="e.g. Photosynthesis"
                    onblur={resolveTopic}
                />
                <button
                    type="button"
                    class="rounded-md border px-3 py-2 text-sm"
                    disabled={resolving_topic || !topic.trim() || !grade_level}
                    onclick={resolveTopic}
                >
                    {resolving_topic ? '…' : 'Narrow'}
                </button>
            </div>
        </label>

        {#if subtopic_candidates.length > 0}
            <div class="space-y-2">
                <p class="text-sm text-muted-foreground">
                    Pick up to 3 subtopics for this lesson
                </p>
                <div class="flex flex-wrap gap-2">
                    {#each subtopic_candidates as candidate}
                        {@const selected = subtopics.includes(candidate.title)}
                        <button
                            type="button"
                            class="rounded-full border px-3 py-1 text-sm
                                   {selected ? 'bg-primary text-primary-foreground border-primary'
                                             : 'bg-background border-input'}"
                            onclick={() => toggleSubtopic(candidate.id, candidate.title)}
                            title={candidate.description}
                        >
                            {candidate.title}
                        </button>
                    {/each}
                </div>
                {#if subtopics.length > 0}
                    <p class="text-xs text-muted-foreground">
                        Selected: {subtopics.join(' · ')}
                    </p>
                {/if}
            </div>
        {/if}

        <label class="grid gap-1 text-sm font-medium">
            <span>
                What have they already covered?
                <span class="text-muted-foreground">(optional)</span>
            </span>
            <input
                class="rounded-md border border-input bg-background px-3 py-2"
                bind:value={prior_knowledge}
                placeholder="e.g. Cell structure, plant parts"
            />
        </label>
    </section>

    <!-- STEP 3 — LESSON SHAPE -->
    <section class="space-y-4">
        <h2 class="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Lesson shape
        </h2>

        <label class="grid gap-1 text-sm font-medium">
            <span>What is this lesson for?</span>
            <select bind:value={lesson_mode}>
                {#each LESSON_MODES as m}
                    <option value={m.value}>{m.label}</option>
                {/each}
            </select>
        </label>

        {#if lesson_mode === 'other'}
            <input
                class="rounded-md border border-input bg-background px-3 py-2 w-full"
                bind:value={lesson_mode_other}
                placeholder="Describe the lesson mode…"
            />
        {/if}

        <label class="grid gap-1 text-sm font-medium">
            <span>What should learners leave able to do?</span>
            <select bind:value={intended_outcome}>
                {#each OUTCOMES as o}
                    <option value={o.value}>{o.label}</option>
                {/each}
            </select>
        </label>

        {#if intended_outcome === 'other'}
            <input
                class="rounded-md border border-input bg-background px-3 py-2 w-full"
                bind:value={intended_outcome_other}
                placeholder="Describe the intended outcome…"
            />
        {/if}
    </section>

    <!-- STEP 4 — CLASS PROFILE -->
    <section class="space-y-4">
        <h2 class="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Your class
        </h2>

        <div class="grid gap-3 sm:grid-cols-2">
            <label class="grid gap-1 text-sm font-medium">
                <span>Overall level</span>
                <select bind:value={learner_level}>
                    {#each LEARNER_LEVELS as l}
                        <option value={l.value}>{l.label}</option>
                    {/each}
                </select>
            </label>

            <label class="grid gap-1 text-sm font-medium">
                <span>Reading level</span>
                <select bind:value={reading_level}>
                    {#each READING_LEVELS as r}
                        <option value={r.value}>{r.label}</option>
                    {/each}
                </select>
            </label>

            <label class="grid gap-1 text-sm font-medium">
                <span>Language support</span>
                <select bind:value={language_support}>
                    {#each LANGUAGE_OPTIONS as l}
                        <option value={l.value}>{l.label}</option>
                    {/each}
                </select>
            </label>

            <label class="grid gap-1 text-sm font-medium">
                <span>Prior knowledge</span>
                <select bind:value={prior_knowledge_level}>
                    {#each PRIOR_KNOWLEDGE_OPTIONS as p}
                        <option value={p.value}>{p.label}</option>
                    {/each}
                </select>
            </label>
        </div>

        <!-- Support needs — checkboxes + Other -->
        <div class="space-y-2">
            <p class="text-sm font-medium">Support needs</p>
            <div class="flex flex-wrap gap-3">
                {#each SUPPORT_OPTIONS as s}
                    <label class="flex items-center gap-2 text-sm">
                        <input
                            type="checkbox"
                            checked={support_needs.includes(s.value)}
                            onchange={() => toggleSupport(s.value)}
                        />
                        {s.label}
                    </label>
                {/each}
            </div>
            <!-- Other support need -->
            <div class="flex gap-2">
                <input
                    class="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm"
                    bind:value={support_other}
                    placeholder="Other support need…"
                    onkeydown={(e) => e.key === 'Enter' && addSupportOther()}
                />
                <button
                    type="button"
                    class="rounded-md border px-3 py-2 text-sm"
                    onclick={addSupportOther}
                    disabled={!support_other.trim()}
                >
                    Add
                </button>
            </div>
            {#if support_needs.filter(s => !SUPPORT_OPTIONS.map(o=>o.value).includes(s)).length > 0}
                <div class="flex flex-wrap gap-2">
                    {#each support_needs.filter(s => !SUPPORT_OPTIONS.map(o=>o.value).includes(s)) as custom}
                        <span class="rounded-full bg-muted px-3 py-1 text-xs">
                            {custom}
                            <button onclick={() => toggleSupport(custom)}>×</button>
                        </span>
                    {/each}
                </div>
            {/if}
        </div>

        <!-- Learning preferences — optional -->
        <div class="space-y-2">
            <p class="text-sm font-medium">
                Learning preferences
                <span class="text-muted-foreground">(optional)</span>
            </p>
            <div class="flex flex-wrap gap-3">
                {#each LEARNING_PREFERENCES as pref}
                    <label class="flex items-center gap-2 text-sm">
                        <input
                            type="checkbox"
                            checked={learning_preferences.includes(pref.value)}
                            onchange={() => togglePreference(pref.value)}
                        />
                        {pref.label}
                    </label>
                {/each}
            </div>
        </div>
    </section>

    <!-- STEP 5 — OPTIONAL INTENT -->
    <section class="space-y-2">
        <h2 class="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Anything else? <span class="text-muted-foreground font-normal">(optional)</span>
        </h2>
        <textarea
            class="w-full min-h-[80px] rounded-md border border-input bg-background px-3 py-2 text-sm"
            bind:value={free_text}
            placeholder="Any specific angles, examples, or constraints to include…"
        />
    </section>

    <button
        type="button"
        disabled={!canSubmit}
        onclick={() => onSubmit(buildForm())}
        class="w-full rounded-md bg-primary px-4 py-3 text-sm font-semibold
               text-primary-foreground disabled:opacity-50"
    >
        Build my lesson plan
    </button>
</div>
```

---

## Signal extractor update

With this richer form, the signal extractor's job shrinks dramatically.
Update `SIGNAL_SYSTEM` in `prompts.py`:

```
You extract the teaching topic and goal from a structured teacher form.
The form already provides lesson_mode, learner_level, support_needs,
prior_knowledge_level, intended_outcome, and subtopics.
Do NOT re-infer these — read them from the form fields directly.
Your only job is to confirm the topic, extract the specific concept being
taught, and summarise the teacher_goal in one clear sentence.
Return a V3SignalSummary with high confidence unless the topic field
is genuinely ambiguous (missing or contradictory).
Missing signals should be empty unless topic is unclear.
```

---

## Lens mapping from form fields

The Lesson Architect can now read these directly without inference:

```python
# In build_architect_system_prompt() or the user prompt builder:
def form_to_lens_hints(form: V3InputForm) -> str:
    hints = [f"lesson_mode: {form.lesson_mode}"]
    if form.lesson_mode_other:
        hints.append(f"lesson_mode detail: {form.lesson_mode_other}")
    hints.append(f"learner_level: {form.learner_level}")
    hints.append(f"reading_level: {form.reading_level}")
    hints.append(f"language_support: {form.language_support}")
    hints.append(f"prior_knowledge_level: {form.prior_knowledge_level}")
    if form.support_needs:
        hints.append(f"support_needs: {', '.join(form.support_needs)}")
    if form.learning_preferences:
        hints.append(f"learning_preferences: {', '.join(form.learning_preferences)}")
    if form.subtopics:
        hints.append(f"subtopics: {', '.join(form.subtopics)}")
    if form.prior_knowledge:
        hints.append(f"prior_knowledge: {form.prior_knowledge}")
    return "\n".join(hints)
```

Inject this into the user prompt sent to the Lesson Architect alongside
signals and clarification answers.

---

## Subtopic resolution — reuse v2 backend endpoint

The existing `POST /api/v1/planning/brief/topic` endpoint returns
`TopicResolutionResult` with `candidate_subtopics`. Reuse it directly.

Helper to convert grade string to grade_level enum:

```typescript
function toGradeLevelEnum(grade: string): string {
    const map: Record<string, string> = {
        'Kindergarten': 'kindergarten',
        'Grade 1': 'grade_1', 'Grade 2': 'grade_2', 'Grade 3': 'grade_3',
        'Grade 4': 'grade_4', 'Grade 5': 'grade_5', 'Grade 6': 'grade_6',
        'Grade 7': 'grade_7', 'Grade 8': 'grade_8', 'Grade 9': 'grade_9',
        'Grade 10': 'grade_10', 'Grade 11': 'grade_11', 'Grade 12': 'grade_12',
    };
    return map[grade] ?? 'mixed';
}

function toGradeBand(grade: string): string {
    if (['Kindergarten','Grade 1','Grade 2','Grade 3','Grade 4','Grade 5'].includes(grade))
        return 'early_elementary';
    if (['Grade 6','Grade 7','Grade 8'].includes(grade)) return 'middle_school';
    if (['Grade 9','Grade 10','Grade 11','Grade 12'].includes(grade)) return 'high_school';
    return 'mixed';
}
```

---

## What the LLM no longer needs to infer

Before this patch:
```
Free text → LLM infers lesson_mode, learner_level, support_needs,
             prior_knowledge, reading_level, language_support, subtopics
```

After this patch:
```
Structured form → LLM reads all of the above directly
Free text → supplemental detail only (optional)
```

Clarification is now exceptional — only fires if the topic field itself
is too vague to plan from. In practice, with grade + subject + subtopics
all set, it should almost never fire.

---

## Verification

```
□ Duration select shows 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 75, 90
□ Grade level shows Kindergarten through Grade 12 only
□ Topic "Narrow" button calls /api/v1/planning/brief/topic
□ Subtopic candidates appear as pill buttons after resolution
□ Teacher can select up to 3 subtopics
□ lesson_mode "Other" reveals a text input
□ intended_outcome "Other" reveals a text input
□ Support needs checkboxes + custom Other text input work correctly
□ Learning preferences checkboxes are optional and multi-select
□ Step 5 free_text is optional — form can submit without it
□ buildForm() produces a valid V3InputForm
□ Blueprint generation receives all form fields via the user prompt
□ lesson_mode in blueprint matches form value — not re-inferred
□ Clarification fires for <5% of well-filled briefs
```

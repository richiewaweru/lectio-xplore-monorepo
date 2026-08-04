# Textbook Generator v3 — Proposal 4: Frontend

## Purpose

Proposals 1–3 delivered the complete v3 backend pipeline:
Signal Extractor → Lesson Architect → Blueprint → WorkOrders →
Executors → DraftPack → Coherence Reviewer → Finalised Resource.

Proposal 4 delivers the teacher-facing frontend that drives that pipeline.
The existing eleven-step brief builder is replaced with a minimal input
surface — three form fields and one free-text box — followed by a
signal confirmation, a clarification conversation, a blueprint preview,
and a streaming canvas that fills in component by component as generation
runs.

**Scope:** v3 Studio page · Input surface · Signal confirmation UI ·
Clarification UI · Blueprint preview card · Streaming canvas skeleton ·
Three new SSE event handlers · Subtle patch indicator

**Out of scope:** Staging environment · v2 brief builder changes ·
PDF download · Lesson Builder integration · Auth changes

**Prerequisite:** Proposals 1–3 complete and verified. All backend
SSE events emitting correctly. `POST /api/v1/v3/signals`,
`POST /api/v1/v3/blueprint`, `POST /api/v1/v3/generate` all working.

**Codebase:** Textbook Generator frontend only. No new backend
architecture. Backend contract mismatches (DTOs, event shapes) should
be fixed by aligning with Proposals 1–3 outputs only.
No Lectio changes. v2 is on its own branch — no coexistence concerns.

**Convention note:** Follow the existing project's Svelte state and store
patterns. Do not introduce Svelte 5 runes unless the repo already uses them.
Reuse existing API/SSE fetch helpers from the project if present.
If not present, create a small v3-local helper in `src/lib/api/v3.ts`.

---

## V3 Frontend Principle

The v2 brief builder asks the teacher to think like a curriculum designer —
eleven steps, dropdowns, class profile fields, support selectors.
The v3 input surface asks the teacher to describe what they want.
The agent does the thinking.

```
v2: Teacher fills in the system's mental model
v3: Teacher describes their intent. Agent builds the plan.
```

Everything the teacher touches in v3 is either:
- A form field with a finite answer (year group, subject, duration)
- Free text describing intent
- A plain-language confirmation or correction
- A one-click approval or plain-language adjustment

No dropdowns for pack type. No class profile fields. No support selectors.
No resource type picker. The agent derives all of that.

---

## Route

v3 replaces the studio directly. v2 is on its own branch and is
unaffected. No coexistence routing needed.

```
/studio  → V3Studio page (this proposal)
```

---

## File Structure

All new files live in the v3 frontend directory.

```
frontend/src/
  routes/
    studio/
      +page.svelte                  # V3Studio page shell

  lib/
    components/
      studio/
        V3InputSurface.svelte       # 3 form fields + free text box
        V3SignalConfirmation.svelte  # system understanding → teacher correction
        V3Clarification.svelte      # 1–2 question chat UI
        V3BlueprintPreview.svelte   # full plan card — approve / adjust
        V3Canvas.svelte             # skeleton + component fill
        V3CanvasSection.svelte      # one section placeholder → filled
        V3CanvasComponent.svelte    # one component placeholder → filled
        V3CanvasVisual.svelte       # one visual placeholder → filled
        V3PatchIndicator.svelte     # subtle highlight on repaired component

    api/
      v3.ts                         # API calls for v3 endpoints

    stores/
      v3-studio.svelte.ts           # v3 page state store

    types/
      v3.ts                         # v3-specific TypeScript types
```

---

## TypeScript Types

**File:** `frontend/src/lib/types/v3.ts`

```typescript
export interface V3InputForm {
  year_group: string       // e.g. "Year 6"
  subject: string          // e.g. "Mathematics"
  duration_minutes: number // 30 | 50 | 60 | 90
  free_text: string
}

export interface V3SignalSummary {
  topic: string
  subtopic: string | null
  prior_knowledge: string[]
  learner_needs: string[]
  teacher_goal: string
  inferred_resource_type: string
  confidence: 'low' | 'medium' | 'high'
  missing_signals: string[]
}

export interface V3ClarificationQuestion {
  question: string
  reason: string
  optional: boolean
}

export interface V3ClarificationAnswer {
  question: string
  answer: string
}

export interface V3AppliedLens {
  id: string
  label: string
  reason: string
  effects: string[]
}

export interface V3SectionPlanItem {
  id: string
  title: string
  order: number
  learning_intent: string
  components: V3ComponentPlan[]
  visual_required: boolean
}

export interface V3ComponentPlan {
  component_id: string
  teacher_label: string       // shown to teacher — never component_id
  content_intent: string
}

export interface V3QuestionPlan {
  id: string
  difficulty: 'warm' | 'medium' | 'cold' | 'transfer'
  expected_answer: string
  diagram_required: boolean
  attaches_to_section_id: string
}

export interface V3AnchorExample {
  label: string
  facts: Record<string, string>
  correct_result: string | null
  reuse_scope: string
}

// BlueprintPreviewDTO — slim frontend representation of ProductionBlueprint.
// The backend returns this DTO from POST /api/v1/v3/blueprint, not the
// full internal ProductionBlueprint. This keeps the UI decoupled from
// backend schema evolution.
export interface BlueprintPreviewDTO {
  blueprint_id: string
  resource_type: string
  title: string
  lenses: V3AppliedLens[]
  anchor: V3AnchorExample | null
  section_plan: V3SectionPlanItem[]
  question_plan: V3QuestionPlan[]
  register_summary: string   // e.g. "Simple · Friendly · Define terms first"
  support_summary: string[]  // e.g. ["EAL support", "Short sentences"]
}

// Canvas state types

export type ComponentStatus = 'pending' | 'generating' | 'ready' | 'patched' | 'failed'

export interface CanvasComponent {
  id: string
  teacher_label: string
  status: ComponentStatus
  data: Record<string, unknown> | null
}

export interface CanvasVisual {
  id: string
  status: ComponentStatus
  image_url: string | null
  frame_index: number | null
}

export interface CanvasSection {
  id: string
  title: string
  teacher_labels: string   // comma-joined component labels
  order: number
  components: CanvasComponent[]
  visual: CanvasVisual | null
  questions: Array<{
    id: string
    difficulty: string
    status: ComponentStatus
    data: Record<string, unknown> | null
  }>
}
```

---

## API Client

**File:** `frontend/src/lib/api/v3.ts`

```typescript
import { fetchJson, connectSSE } from './client'

// Step 1: extract signals from teacher input
export async function extractSignals(
  form: V3InputForm
): Promise<V3SignalSummary> {
  return fetchJson('POST', '/api/v1/v3/signals', form)
}

// Step 2: get clarification questions (if needed)
export async function getClarifications(
  signals: V3SignalSummary,
  form: V3InputForm
): Promise<V3ClarificationQuestion[]> {
  return fetchJson('POST', '/api/v1/v3/clarify', { signals, form })
}

// Step 3: generate blueprint from signals + answers
export async function generateBlueprint(payload: {
  signals: V3SignalSummary
  form: V3InputForm
  clarification_answers: V3ClarificationAnswer[]
}): Promise<BlueprintPreviewDTO> {
  return fetchJson('POST', '/api/v1/v3/blueprint', payload)
}

// Step 4: adjust blueprint with plain language instruction
export async function adjustBlueprint(payload: {
  blueprint_id: string
  adjustment: string
}): Promise<BlueprintPreviewDTO> {
  return fetchJson('POST', '/api/v1/v3/blueprint/adjust', payload)
}

// Step 5: start generation — returns SSE stream
export function startGeneration(
  blueprint_id: string,
  generation_id: string,
  handlers: {
    onComponentReady: (data: ComponentReadyEvent) => void
    onVisualReady: (data: VisualReadyEvent) => void
    onComponentPatched: (data: ComponentPatchedEvent) => void
    onCoherenceStatus: (data: CoherenceStatusEvent) => void
    onResourceFinalised: (data: ResourceFinalisedEvent) => void
    onError: (err: Error) => void
  }
): () => void {
  return connectSSE(
    `/api/v1/v3/generate`,
    { blueprint_id, generation_id },
    handlers
  )
}

// SSE event payload types
export interface ComponentReadyEvent {
  component_id: string
  section_id: string
  position: number
  section_field: string
  data: Record<string, unknown>
}

export interface VisualReadyEvent {
  visual_id: string
  attaches_to: string
  frame_index: number | null
  image_url: string
}

export interface QuestionReadyEvent {
  question_id: string
  section_id: string
  difficulty: string
  data: Record<string, unknown>
}

export interface ComponentPatchedEvent {
  component_id: string
  section_id: string
  data: Record<string, unknown>
}

export interface AnswerKeyReadyEvent {
  entries: Array<{ question_id: string; answer: string; working?: string }>
  style: string
}

export interface CoherenceStatusEvent {
  status: string
  blocking_count: number
  repair_target_count: number
}

export interface ResourceFinalisedEvent {
  status: string
}
```

---

## Page State Store

**File:** `frontend/src/lib/stores/v3-studio.svelte.ts`

```typescript
type V3Stage =
  | 'input'          // teacher fills form + free text
  | 'confirming'     // system shows what it understood
  | 'clarifying'     // 1–2 questions
  | 'planning'       // Lesson Architect running
  | 'reviewing'      // teacher reviews blueprint
  | 'generating'     // executors running + canvas filling
  | 'finalising'     // coherence review running
  | 'complete'       // resource ready

export const v3Stage = $state<V3Stage>('input')
export const v3Form = $state<V3InputForm | null>(null)
export const v3Signals = $state<V3SignalSummary | null>(null)
export const v3Clarifications = $state<V3ClarificationQuestion[]>([])
export const v3Answers = $state<V3ClarificationAnswer[]>([])
export const v3Blueprint = $state<BlueprintPreviewDTO | null>(null)
export const v3Canvas = $state<CanvasSection[]>([])
export const v3Error = $state<string | null>(null)
```

---

## Step 1 — V3 Studio Page Shell

**File:** `frontend/src/routes/studio/+page.svelte`

The page shell manages stage transitions and renders the correct
component for each stage. One component visible at a time.

```svelte
<script lang="ts">
  import V3InputSurface from '$lib/components/studio/V3InputSurface.svelte'
  import V3SignalConfirmation from '$lib/components/studio/V3SignalConfirmation.svelte'
  import V3Clarification from '$lib/components/studio/V3Clarification.svelte'
  import V3BlueprintPreview from '$lib/components/studio/V3BlueprintPreview.svelte'
  import V3Canvas from '$lib/components/studio/V3Canvas.svelte'
  import {
    v3Stage, v3Form, v3Signals, v3Clarifications,
    v3Answers, v3Blueprint, v3Canvas, v3Error
  } from '$lib/stores/v3-studio.svelte'
  import {
    extractSignals, getClarifications, generateBlueprint,
    adjustBlueprint, startGeneration
  } from '$lib/api/v3'
</script>

<div class="v3-studio">
  {#if $v3Stage === 'input'}
    <V3InputSurface onSubmit={handleInputSubmit} />

  {:else if $v3Stage === 'confirming'}
    <V3SignalConfirmation
      signals={$v3Signals}
      onConfirm={handleSignalsConfirmed}
      onCorrect={handleSignalCorrection}
    />

  {:else if $v3Stage === 'clarifying'}
    <V3Clarification
      questions={$v3Clarifications}
      onAnswered={handleClarificationAnswered}
    />

  {:else if $v3Stage === 'planning'}
    <div class="v3-planning-state">
      <p>Planning your lesson...</p>
    </div>

  {:else if $v3Stage === 'reviewing'}
    <V3BlueprintPreview
      blueprint={$v3Blueprint}
      onApprove={handleBlueprintApproved}
      onAdjust={handleBlueprintAdjust}
    />

  {:else if $v3Stage === 'generating' || $v3Stage === 'finalising'}
    <V3Canvas
      sections={$v3Canvas}
      stage={$v3Stage}
    />

  {:else if $v3Stage === 'complete'}
    <V3Canvas
      sections={$v3Canvas}
      stage="complete"
    />
  {/if}

  {#if $v3Error}
    <p class="v3-error" role="alert">{$v3Error}</p>
  {/if}
</div>
```

---

## Step 2 — Input Surface

**File:** `frontend/src/lib/components/studio/V3InputSurface.svelte`

Three form fields and one free-text box. Nothing else.

```svelte
<script lang="ts">
  import type { V3InputForm } from '$lib/types/v3'

  let { onSubmit }: { onSubmit: (form: V3InputForm) => void } = $props()

  let year_group = $state('')
  let subject = $state('')
  let duration_minutes = $state(50)
  let free_text = $state('')

  const YEAR_GROUPS = [
    'Year 1', 'Year 2', 'Year 3', 'Year 4', 'Year 5', 'Year 6',
    'Year 7', 'Year 8', 'Year 9', 'Year 10', 'Year 11', 'Year 12',
    'Grade 6', 'Grade 7', 'Grade 8', 'Grade 9', 'Grade 10',
    'Grade 11', 'Grade 12'
  ]

  const SUBJECTS = [
    'Mathematics', 'English', 'Science', 'Physics',
    'Chemistry', 'Biology', 'History', 'Geography',
    'Economics', 'Computer Science', 'Other'
  ]

  const DURATIONS = [
    { label: '30 min', value: 30 },
    { label: '50 min', value: 50 },
    { label: '60 min', value: 60 },
    { label: '90 min', value: 90 }
  ]

  const canSubmit = $derived(
    year_group !== '' && subject !== '' && free_text.trim().length > 20
  )

  function handleSubmit() {
    if (!canSubmit) return
    onSubmit({ year_group, subject, duration_minutes, free_text })
  }
</script>

<div class="v3-input">
  <header class="v3-input-header">
    <h1>What do you want to teach?</h1>
    <p>Describe what you need and we'll build the plan.</p>
  </header>

  <div class="v3-form-fields">
    <select bind:value={year_group} aria-label="Year group">
      <option value="">Year group</option>
      {#each YEAR_GROUPS as yg}
        <option value={yg}>{yg}</option>
      {/each}
    </select>

    <select bind:value={subject} aria-label="Subject">
      <option value="">Subject</option>
      {#each SUBJECTS as s}
        <option value={s}>{s}</option>
      {/each}
    </select>

    <select bind:value={duration_minutes} aria-label="Duration">
      {#each DURATIONS as d}
        <option value={d.value}>{d.label}</option>
      {/each}
    </select>
  </div>

  <textarea
    bind:value={free_text}
    placeholder="Describe what you want to teach and what you want learners to do.
For example: I need to teach my Year 6 class area of compound shapes.
They've done basic area before but this is their first time with L-shapes.
A few EAL students in the group."
    rows={6}
    aria-label="Teaching intent"
  ></textarea>

  <button
    onclick={handleSubmit}
    disabled={!canSubmit}
    class="v3-submit"
  >
    Continue
  </button>
</div>
```

---

## Step 3 — Signal Confirmation

**File:** `frontend/src/lib/components/studio/V3SignalConfirmation.svelte`

Teacher sees what the system understood. Corrects anything wrong
before the Lesson Architect runs. This is the first participation
moment — cheap to fix here, expensive after blueprint generation.

```svelte
<script lang="ts">
  import type { V3SignalSummary } from '$lib/types/v3'

  let {
    signals,
    onConfirm,
    onCorrect
  }: {
    signals: V3SignalSummary
    onConfirm: () => void
    onCorrect: (field: string, value: string) => void
  } = $props()
</script>

<div class="v3-signal-confirmation">
  <h2>Here's what I understood</h2>
  <p class="v3-signal-subtitle">
    Correct anything before I plan the lesson.
  </p>

  <dl class="v3-signals">
    <div class="v3-signal-row">
      <dt>Topic</dt>
      <dd>{signals.topic}</dd>
    </div>

    {#if signals.subtopic}
      <div class="v3-signal-row">
        <dt>Focus</dt>
        <dd>{signals.subtopic}</dd>
      </div>
    {/if}

    {#if signals.prior_knowledge.length}
      <div class="v3-signal-row">
        <dt>Prior knowledge</dt>
        <dd>{signals.prior_knowledge.join(', ')}</dd>
      </div>
    {/if}

    <div class="v3-signal-row">
      <dt>Goal</dt>
      <dd>{signals.teacher_goal}</dd>
    </div>

    <div class="v3-signal-row">
      <dt>Resource</dt>
      <dd>{signals.inferred_resource_type.replace(/_/g, ' ')}</dd>
    </div>

    {#if signals.learner_needs.length}
      <div class="v3-signal-row">
        <dt>Learner needs</dt>
        <dd>{signals.learner_needs.join(', ')}</dd>
      </div>
    {/if}
  </dl>

  {#if signals.missing_signals.length}
    <p class="v3-missing-notice">
      I'll ask about: {signals.missing_signals.join(', ')}
    </p>
  {/if}

  <div class="v3-confirmation-actions">
    <button onclick={onConfirm} class="v3-primary">
      That's right — continue
    </button>
    <button
      onclick={() => onCorrect('free_text', '')}
      class="v3-secondary"
    >
      Something's wrong — let me rephrase
    </button>
  </div>
</div>
```

---

## Step 4 — Clarification UI

**File:** `frontend/src/lib/components/studio/V3Clarification.svelte`

1–2 questions maximum. Conversational — not a form.
Teacher types plain-language answers.

```svelte
<script lang="ts">
  import type {
    V3ClarificationQuestion,
    V3ClarificationAnswer
  } from '$lib/types/v3'

  let {
    questions,
    onAnswered
  }: {
    questions: V3ClarificationQuestion[]
    onAnswered: (answers: V3ClarificationAnswer[]) => void
  } = $props()

  let answers = $state<string[]>(questions.map(() => ''))

  const allAnswered = $derived(
    questions.every((q, i) => q.optional || answers[i].trim().length > 0)
  )

  function handleSubmit() {
    const result: V3ClarificationAnswer[] = questions.map((q, i) => ({
      question: q.question,
      answer: answers[i]
    }))
    onAnswered(result)
  }
</script>

<div class="v3-clarification">
  <h2>Just a couple of things</h2>

  {#each questions as q, i}
    <div class="v3-clarification-question">
      <label for="clarify-{i}">{q.question}</label>
      <input
        id="clarify-{i}"
        type="text"
        bind:value={answers[i]}
        placeholder="Type your answer..."
      />
    </div>
  {/each}

  <button onclick={handleSubmit} disabled={!allAnswered} class="v3-primary">
    Continue
  </button>
</div>
```

---

## Step 5 — Blueprint Preview

**File:** `frontend/src/lib/components/studio/V3BlueprintPreview.svelte`

The second and most important teacher participation moment.
Teacher reads the full lesson plan before anything is generated.
Uses `teacher_label` everywhere — never `component_id`.
Approve in one click or adjust in plain language.

```svelte
<script lang="ts">
  import type { BlueprintPreviewDTO } from '$lib/types/v3'

  let {
    blueprint,
    onApprove,
    onAdjust
  }: {
    blueprint: BlueprintPreviewDTO
    onApprove: () => void
    onAdjust: (instruction: string) => void
  } = $props()

  let adjustText = $state('')
  let showAdjust = $state(false)

  const difficultyLabel: Record<string, string> = {
    warm: 'Warm',
    medium: 'Medium',
    cold: 'Cold',
    transfer: 'Transfer'
  }
</script>

<div class="v3-blueprint">
  <header class="v3-blueprint-header">
    <div>
      <p class="v3-eyebrow">Lesson plan</p>
      <h2>{blueprint.resource_plan.title}</h2>
    </div>
    <span class="v3-resource-type">
      {blueprint.resource_plan.resource_type.replace(/_/g, ' ')}
    </span>
  </header>

  <!-- Lenses applied -->
  {#if blueprint.lenses.length}
    <section class="v3-blueprint-section">
      <h3>How I planned this</h3>
      <ul class="v3-lenses">
        {#each blueprint.lenses as lens}
          <li class="v3-lens">
            <strong>{lens.label}</strong>
            <span class="v3-lens-reason">{lens.reason}</span>
            {#if lens.effects.length}
              <ul class="v3-lens-effects">
                {#each lens.effects as effect}
                  <li>{effect}</li>
                {/each}
              </ul>
            {/if}
          </li>
        {/each}
      </ul>
    </section>
  {/if}

  <!-- Anchor example -->
  {#if blueprint.anchor}
    <section class="v3-blueprint-section">
      <h3>Anchor example</h3>
      <div class="v3-anchor">
        <strong>{blueprint.anchor.label}</strong>
        <dl class="v3-anchor-facts">
          {#each Object.entries(blueprint.anchor.facts) as [key, val]}
            <div>
              <dt>{key.replace(/_/g, ' ')}</dt>
              <dd>{val}</dd>
            </div>
          {/each}
          {#if blueprint.anchor.correct_result}
            <div class="v3-anchor-answer">
              <dt>Correct answer</dt>
              <dd>{blueprint.anchor.correct_result}</dd>
            </div>
          {/if}
        </dl>
        <p class="v3-anchor-scope">
          Used in: {blueprint.anchor.reuse_scope.replace(/_/g, ' ')}
        </p>
      </div>
    </section>
  {/if}

  <!-- Section plan -->
  <section class="v3-blueprint-section">
    <h3>Lesson sections</h3>
    <ol class="v3-section-plan">
      {#each blueprint.section_plan as section}
        <li class="v3-section-plan-item">
          <div class="v3-section-plan-header">
            <strong>{section.title}</strong>
            <span class="v3-component-labels">
              {section.components.map(c => c.teacher_label).join(' · ')}
            </span>
          </div>
          <p class="v3-learning-intent">{section.learning_intent}</p>
        </li>
      {/each}
    </ol>
  </section>

  <!-- Question plan -->
  {#if blueprint.question_plan.length}
    <section class="v3-blueprint-section">
      <h3>Practice questions</h3>
      <table class="v3-question-plan">
        <thead>
          <tr>
            <th>Question</th>
            <th>Difficulty</th>
            <th>Diagram</th>
            <th>Answer</th>
          </tr>
        </thead>
        <tbody>
          {#each blueprint.question_plan as q, i}
            <tr>
              <td>Q{i + 1}</td>
              <td>
                <span class="v3-difficulty v3-difficulty-{q.difficulty}">
                  {difficultyLabel[q.difficulty] ?? q.difficulty}
                </span>
              </td>
              <td>{q.diagram_required ? 'Yes' : '—'}</td>
              <td class="v3-expected-answer">{q.expected_answer}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>
  {/if}

  <!-- Approve / adjust -->
  <div class="v3-blueprint-actions">
    <button onclick={onApprove} class="v3-approve">
      Approve and generate
    </button>
    <button
      onclick={() => showAdjust = !showAdjust}
      class="v3-secondary"
    >
      Request changes
    </button>
  </div>

  {#if showAdjust}
    <div class="v3-adjust">
      <textarea
        bind:value={adjustText}
        placeholder="Describe what you'd like to change.
For example: Make Q4 harder. Use a T-shape instead of an L-shape."
        rows={3}
      ></textarea>
      <button
        onclick={() => { onAdjust(adjustText); adjustText = ''; showAdjust = false }}
        disabled={adjustText.trim().length === 0}
        class="v3-primary"
      >
        Update plan
      </button>
    </div>
  {/if}
</div>
```

---

## Step 6 — Streaming Canvas

**File:** `frontend/src/lib/components/studio/V3Canvas.svelte`

The canvas renders immediately on blueprint approval as a skeleton —
all sections in blueprint order with placeholders. Components fill
in as SSE events arrive, in whatever order executors complete.
Positional order is always correct because the skeleton is built
from the blueprint.

```svelte
<script lang="ts">
  import type { CanvasSection } from '$lib/types/v3'
  import V3CanvasSection from '$lib/components/studio/V3CanvasSection.svelte'

  let {
    sections,
    stage
  }: {
    sections: CanvasSection[]
    stage: string
  } = $props()

  const progressLabel: Record<string, string> = {
    generating: 'Writing your lesson...',
    finalising: 'Checking consistency...',
    complete: 'Resource ready'
  }
</script>

<div class="v3-canvas">
  <div class="v3-canvas-status" role="status" aria-live="polite">
    {progressLabel[stage] ?? ''}
  </div>

  <div class="v3-canvas-sections">
    {#each sections as section (section.id)}
      <V3CanvasSection {section} />
    {/each}
  </div>
</div>
```

**File:** `frontend/src/lib/components/studio/V3CanvasSection.svelte`

```svelte
<script lang="ts">
  import type { CanvasSection } from '$lib/types/v3'
  import V3CanvasComponent from '$lib/components/studio/V3CanvasComponent.svelte'
  import V3CanvasVisual from '$lib/components/studio/V3CanvasVisual.svelte'

  let { section }: { section: CanvasSection } = $props()
</script>

<div class="v3-canvas-section" id="section-{section.id}">
  <div class="v3-canvas-section-header">
    <span class="v3-canvas-section-title">{section.title}</span>
    <span class="v3-canvas-section-labels">{section.teacher_labels}</span>
  </div>

  {#if section.visual}
    <V3CanvasVisual visual={section.visual} />
  {/if}

  {#each section.components as component (component.id)}
    <V3CanvasComponent {component} />
  {/each}

  {#each section.questions as question (question.id)}
    <div class="v3-canvas-question v3-status-{question.status}">
      <span class="v3-question-difficulty">{question.difficulty}</span>
      {#if question.status === 'pending'}
        <div class="v3-skeleton v3-skeleton-question"></div>
      {:else if question.status === 'ready'}
        <!-- question data rendered via GenerationView pattern -->
      {/if}
    </div>
  {/each}
</div>
```

**File:** `frontend/src/lib/components/studio/V3CanvasComponent.svelte`

```svelte
<script lang="ts">
  import type { CanvasComponent } from '$lib/types/v3'
  import V3PatchIndicator from '$lib/components/studio/V3PatchIndicator.svelte'

  let { component }: { component: CanvasComponent } = $props()
</script>

<div class="v3-canvas-component v3-status-{component.status}">
  {#if component.status === 'pending'}
    <div class="v3-component-label">{component.teacher_label}</div>
    <div class="v3-skeleton"></div>

  {:else if component.status === 'generating'}
    <div class="v3-component-label">{component.teacher_label}</div>
    <div class="v3-skeleton v3-skeleton-active"></div>

  {:else if component.status === 'ready' || component.status === 'patched'}
    {#if component.status === 'patched'}
      <V3PatchIndicator />
    {/if}
    <!--
      Render component.data using the existing Lectio component resolver.
      This is the same resolver used in GenerationView / LectioDocumentView.
      Do NOT invent a new renderer — reuse what exists in the project.

      The resolver maps component_id → Lectio Svelte component, then
      passes component.data as props. The section_field from the
      GeneratedComponentBlock tells the resolver which content key to use.

      If the existing resolver is not directly importable here, create a
      thin V3ComponentRenderer.svelte that wraps it.
    -->
    <div class="v3-component-content">
      <V3ComponentRenderer
        componentId={component.id}
        data={component.data}
      />
    </div>

  {:else if component.status === 'failed'}
    <div class="v3-component-error">
      Failed to generate {component.teacher_label}
    </div>
  {/if}
</div>
```

**File:** `frontend/src/lib/components/studio/V3PatchIndicator.svelte`

```svelte
<script lang="ts">
  import { onMount } from 'svelte'

  let visible = $state(true)

  onMount(() => {
    const timer = setTimeout(() => { visible = false }, 2000)
    return () => clearTimeout(timer)
  })
</script>

{#if visible}
  <div class="v3-patch-indicator" aria-label="Refined">
    refined
  </div>
{/if}

<style>
  .v3-patch-indicator {
    font-size: 0.7rem;
    color: var(--color-text-success);
    opacity: 1;
    transition: opacity 0.6s ease;
    animation: v3-patch-fade 2s ease forwards;
  }

  @keyframes v3-patch-fade {
    0% { opacity: 1; }
    70% { opacity: 1; }
    100% { opacity: 0; }
  }
</style>
```

---

## Step 7 — Stage Transition Logic

**File:** `frontend/src/routes/studio/+page.svelte` (handlers)

```typescript
// 1. Teacher submits form
async function handleInputSubmit(form: V3InputForm) {
  v3Form.set(form)
  v3Stage.set('confirming')
  const signals = await extractSignals(form)
  v3Signals.set(signals)
}

// 2. Teacher confirms signals
async function handleSignalsConfirmed() {
  const signals = v3Signals.current
  if (!signals) return

  if (signals.missing_signals.length > 0) {
    const questions = await getClarifications(signals, v3Form.current!)
    v3Clarifications.set(questions)
    v3Stage.set('clarifying')
  } else {
    await runLessonArchitect()
  }
}

// 3. Teacher corrects signals — go back to input
function handleSignalCorrection() {
  v3Stage.set('input')
}

// 4. Teacher answers clarification questions
async function handleClarificationAnswered(answers: V3ClarificationAnswer[]) {
  v3Answers.set(answers)
  await runLessonArchitect()
}

// 5. Run Lesson Architect → get blueprint
async function runLessonArchitect() {
  v3Stage.set('planning')
  const blueprint = await generateBlueprint({
    signals: v3Signals.current!,
    form: v3Form.current!,
    clarification_answers: v3Answers.current
  })
  v3Blueprint.set(blueprint)
  v3Stage.set('reviewing')
}

// 6. Teacher approves blueprint → build skeleton + start generation
async function handleBlueprintApproved() {
  const blueprint = v3Blueprint.current!

  // Build canvas skeleton from blueprint — instant, before first SSE event
  v3Canvas.set(buildCanvasSkeleton(blueprint))
  v3Stage.set('generating')

  // Open SSE stream
  startGeneration(blueprint.blueprint_id, crypto.randomUUID(), {
    onComponentReady(data) {
      fillComponent(data.section_id, data.component_id, data.data)
    },
    onVisualReady(data) {
      fillVisual(data.attaches_to, data.image_url, data.frame_index)
    },
    onQuestionReady(data) {
      fillQuestion(data.section_id, data.question_id, data.data)
    },
    onComponentPatched(data) {
      patchComponent(data.section_id, data.component_id, data.data)
    },
    onAnswerKeyReady(_data) {
      // answer key is teacher-facing only — not rendered in student canvas
      // store if needed for download/report view
    },
    onCoherenceReviewStarted() {
      // Point 8: enter finalising on coherence_review_started,
      // not conditionally on blocking count
      v3Stage.set('finalising')
    },
    onCoherenceStatus(_data) {
      // status already set by onCoherenceReviewStarted
    },
    onResourceFinalised() {
      v3Stage.set('complete')
    },
    onError(err) {
      v3Error.set(err.message)
    }
  })
}

// 7. Teacher adjusts blueprint
async function handleBlueprintAdjust(instruction: string) {
  v3Stage.set('planning')
  const revised = await adjustBlueprint({
    blueprint_id: v3Blueprint.current!.blueprint_id,
    adjustment: instruction
  })
  v3Blueprint.set(revised)
  v3Stage.set('reviewing')
}

// Build canvas skeleton from blueprint
function buildCanvasSkeleton(blueprint: BlueprintPreviewDTO): CanvasSection[] {
  return blueprint.section_plan
    .sort((a, b) => a.order - b.order)
    .map(section => ({
      id: section.id,
      title: section.title,
      teacher_labels: section.components.map(c => c.teacher_label).join(' · '),
      order: section.order,
      components: section.components.map(c => ({
        id: c.component_id,
        teacher_label: c.teacher_label,
        status: 'pending' as const,
        data: null
      })),
      visual: section.visual_required
        ? { id: `visual-${section.id}`, status: 'pending', image_url: null, frame_index: null }
        : null,
      questions: blueprint.question_plan
        .filter(q => q.attaches_to_section_id === section.id)
        .map(q => ({ id: q.id, difficulty: q.difficulty, status: 'pending' as const }))
    }))
}

// Canvas fill helpers
function fillComponent(sectionId: string, componentId: string, data: Record<string, unknown>) {
  v3Canvas.update(sections =>
    sections.map(s => s.id !== sectionId ? s : {
      ...s,
      components: s.components.map(c => c.id !== componentId ? c : {
        ...c, status: 'ready', data
      })
    })
  )
}

function fillVisual(sectionId: string, imageUrl: string, frameIndex: number | null) {
  v3Canvas.update(sections =>
    sections.map(s => s.id !== sectionId ? s : {
      ...s,
      visual: s.visual ? { ...s.visual, status: 'ready', image_url: imageUrl, frame_index: frameIndex } : null
    })
  )
}

function fillQuestion(sectionId: string, questionId: string, data: Record<string, unknown>) {
  v3Canvas.update(sections =>
    sections.map(s => s.id !== sectionId ? s : {
      ...s,
      questions: s.questions.map(q => q.id !== questionId ? q : {
        ...q, status: 'ready' as const, data
      })
    })
  )
}

function patchComponent(sectionId: string, componentId: string, data: Record<string, unknown>) {
  v3Canvas.update(sections =>
    sections.map(s => s.id !== sectionId ? s : {
      ...s,
      components: s.components.map(c => c.id !== componentId ? c : {
        ...c, status: 'patched' as const, data
      })
    })
  )
}
```

---

## Implementation Order

All steps are sequential.

```
Step 1 — Types and API client
  Write v3.ts types
  Write v3.ts API client
  Write v3-studio.svelte.ts store
  No UI yet — verify types compile

Step 2 — Page shell and routing
  Create /studio/v3/+page.svelte
  All stage transitions wired but components are stubs
  Verify route is accessible

Step 3 — Input surface
  Write V3InputSurface.svelte
  Three form fields + textarea
  canSubmit validation
  Connect to extractSignals API call

Step 4 — Signal confirmation
  Write V3SignalConfirmation.svelte
  All signal fields displayed
  Confirm → proceeds, Correct → back to input

Step 5 — Clarification UI
  Write V3Clarification.svelte
  1–2 questions, plain text answers
  optional questions can be skipped
  Connect to runLessonArchitect on submit

Step 6 — Blueprint preview
  Write V3BlueprintPreview.svelte
  teacher_label everywhere — never component_id
  Lenses with concrete effects shown
  Anchor example with facts and correct_result
  Section plan with learning_intent
  Question plan with difficulty + expected_answer
  Approve button → handleBlueprintApproved
  Adjust textarea → handleBlueprintAdjust

Step 7 — Canvas skeleton and fill
  Write V3Canvas.svelte, V3CanvasSection.svelte,
  V3CanvasComponent.svelte, V3CanvasVisual.svelte
  buildCanvasSkeleton from blueprint — renders before first SSE event
  fillComponent, fillVisual, patchComponent handlers
  Skeleton renders instantly on approve click

Step 8 — Patch indicator
  Write V3PatchIndicator.svelte
  Shows on component_patched event
  Fades after 2 seconds — no jarring re-render

Step 9 — Stage transition wiring
  Wire all handlers in page shell
  End-to-end: input → confirm → clarify → plan → review → generate → complete
  Verify skeleton renders before first SSE event arrives
  Verify components fill correct positions regardless of arrival order
```

---

## Non-Negotiable Rules for the Coding Agent

```
1.  Studio page at frontend/src/routes/studio/+page.svelte
    Components under frontend/src/lib/components/studio/
    API client at frontend/src/lib/api/v3.ts
2.  Follow the project's existing Svelte state and store conventions.
    Do not introduce Svelte 5 runes unless the repo already uses them.
3.  Reuse existing API/SSE fetch helpers from the project.
    If not present, create a small helper in src/lib/api/v3.ts only.
4.  Generation uses two steps:
    POST /api/v1/v3/generate → returns generation_id
    GET /api/v1/v3/generations/{generation_id}/events → SSE stream
    Browser EventSource is GET only — do not use POST for SSE.
5.  Backend returns BlueprintPreviewDTO not full ProductionBlueprint.
    Frontend never navigates the internal blueprint schema.
6.  Blueprint preview uses teacher_label everywhere — never component_id.
7.  Component blocks rendered via existing Lectio component resolver —
    do not invent a new renderer. Wrap in V3ComponentRenderer if needed.
8.  Canvas skeleton renders from blueprint on approve click —
    before the first SSE event arrives.
9.  fillComponent / fillQuestion / fillVisual slot by section_id + id —
    never by arrival order.
10. onCoherenceReviewStarted → v3Stage = 'finalising' unconditionally.
    Do not gate on blocking_count.
11. patchComponent fires V3PatchIndicator — fades after 2 seconds.
12. Adjust blueprint sends plain-language instruction to
    POST /api/v1/v3/blueprint/adjust — does not re-run signal extraction.
13. Generation blocked until blueprint explicitly approved.
14. Teacher sees human-readable status labels — never technical event names.
15. SSE error triggers v3Error state — teacher sees plain message.
```

---

## Definition of Done

Proposal 4 is complete when:

```
1.  /studio route renders V3Studio without error
2.  Three form fields + textarea render on input stage
4.  Signal confirmation shows all V3SignalSummary fields
5.  Confirm proceeds to clarification or planning correctly
6.  Correct returns to input stage
7.  Clarification shows 1–2 questions, plain text answers
8.  Optional questions can be skipped
9.  Planning state shows while Lesson Architect runs
10. Blueprint preview uses teacher_label — no component_id visible
11. Lenses show with concrete effects
12. Anchor facts and correct_result shown in blueprint
13. Question plan shows difficulty + expected_answer
14. Approve click renders canvas skeleton before first SSE event
15. Components fill correct positional placeholders as SSE events arrive
16. Questions fill correct section as question_ready events arrive
17. Visuals fill correct section as visual_ready events arrive
18. component_patched shows V3PatchIndicator fading after 2 seconds
19. coherence_review_started sets stage to finalising — always, unconditionally
20. Adjust textarea sends plain instruction, returns revised BlueprintPreviewDTO
21. resource_finalised sets stage to complete
22. v3Error displays plain message on any API or SSE failure
23. Component blocks rendered via existing Lectio resolver — not raw JSON
24. Generation uses POST → generation_id then GET → SSE events
25. End-to-end: input → resource ready — no stage gets stuck
```

# Lectio — Component and Template Harmonisation Spec

## Purpose

This document is a complete implementation brief for Claude Code.
It covers three things in order:

1. New components and type extensions to add to the Lectio library
2. Changes to the `TemplateContract` interface in `template-types.ts`
3. Updated config for all 12 existing templates

This is **Lectio-only work**. Do not touch the planning layer, pipeline,
or any backend files. The scope is entirely within the Lectio npm package
(`src/lib/`) and the export script (`scripts/export-contracts.ts`).

---

## Guiding Principles

Before touching any file, understand these principles:

**Templates declare vocabulary, not layout sequences.**
A template says which components are available and what their budget caps
are. It does not decide which section gets which component — that is the
planning layer's job (outside this scope). Remove anything that implies
a fixed section sequence.

**`always_present` means structurally required, not pedagogically required.**
Only components that every single render of this template absolutely must
have belong in `always_present`. Do not put `practice-stack` here. The
majority of available components should be in `available_components`.

**Budgets are hard caps per lesson, enforced in code not prompts.**
`component_budget` defines the maximum times a heavy component can appear
across all sections of a lesson. The planning layer reads this — the
generator enforces it.

**`signal_affinity` is a scoring input for the planning layer.**
Scores are 0.0–1.0. Higher means this template is a strong fit when the
teacher selects that signal. The planning layer reads these to score
templates without LLM judgment.

---

## Step 1 — Add new TypeScript types to `src/lib/types.ts`

Add the following type definitions. Insert them in the appropriate group
positions, following the existing naming conventions.

### 1a. Extend existing types

**`SectionHeaderContent`** — replace the single `objective` field with
a list:

```typescript
// Remove:
objective: Optional[str] = None  // (Python mirror — change both)

// Add:
objectives: Optional[list[str]] = None  // list of 2–4 learning objectives
```

In TypeScript (`types.ts`):
```typescript
// Remove:
objective?: string

// Add:
objectives?: string[]
```

**`ExplanationCallout`** — add two new callout types:
```typescript
// Current:
type: 'remember' | 'insight' | 'sidenote'

// Updated:
type: 'remember' | 'insight' | 'sidenote' | 'warning' | 'exam-tip'
```

**`QuizContent`** — add true-false support:
```typescript
// Add a new type field to QuizContent:
quiz_type?: 'multiple-choice' | 'true-false'
// When quiz_type is 'true-false', options array should have exactly 2 items: ['True', 'False']
```

**`PracticeProblem`** — add open-ended type:
```typescript
// Add to PracticeProblem:
problem_type?: 'structured' | 'open'
// When problem_type is 'open', the renderer shows write-in lines instead
// of a solution block. Hints still apply.
```

### 1b. New content types (add after existing Group 4 types)

```typescript
// ── GROUP 1 ADDITION — CALLOUT BLOCK ────────────────────────────────────────
export type CalloutVariant = 'info' | 'tip' | 'warning' | 'exam-tip' | 'remember'

export interface CalloutBlockContent {
  variant: CalloutVariant
  heading?: string          // short label, e.g. "Key point"
  body: string              // the callout text, max ~60 words
}

// ── GROUP 1 ADDITION — SUMMARY BLOCK ────────────────────────────────────────
export interface SummaryItem {
  text: string              // one takeaway, max 25 words
}

export interface SummaryBlockContent {
  heading?: string          // defaults to "In summary" if omitted
  items: SummaryItem[]      // 2–5 bullet takeaways
  closing?: string          // optional 1-sentence closing, max 30 words
}

// ── GROUP 4 ADDITION — STUDENT TEXTBOX ──────────────────────────────────────
export interface StudentTextboxContent {
  prompt: string            // the write-in instruction, max 40 words
  lines?: number            // hint for print rendering: how many lines to draw (default 4)
  label?: string            // optional small label above box, e.g. "Your answer"
}

// ── GROUP 4 ADDITION — SHORT ANSWER QUESTION ────────────────────────────────
export interface ShortAnswerContent {
  question: string          // the question text, max 60 words
  marks?: number            // optional mark allocation shown to student
  lines?: number            // lines for print (default 6)
  mark_scheme?: string      // optional teacher-facing answer notes (hidden from student)
}

// ── GROUP 4 ADDITION — FILL IN THE BLANK ────────────────────────────────────
export interface FillInBlankSegment {
  text: string              // prose segment
  is_blank: boolean         // if true, render as a blank
  answer?: string           // the correct word/phrase for this blank
}

export interface FillInBlankContent {
  instruction?: string      // e.g. "Complete the passage using the words below"
  segments: FillInBlankSegment[]
  word_bank?: string[]      // optional list of words to choose from
}

// ── GROUP 1 ADDITION — SECTION DIVIDER ──────────────────────────────────────
export interface SectionDividerContent {
  label: string             // e.g. "Part A", "Extension", "Exam practice"
}

// ── GROUP 2 ADDITION — KEY FACT ─────────────────────────────────────────────
export interface KeyFactContent {
  fact: string              // the prominent fact, formula, or figure — max 20 words
  context?: string          // optional 1-sentence explanation, max 30 words
  source?: string           // optional attribution
}
```

### 1c. Add new fields to `SectionContent`

Add all of the above as optional fields in the `SectionContent` interface:

```typescript
// In SectionContent, add:
callout?: CalloutBlockContent
summary?: SummaryBlockContent
student_textbox?: StudentTextboxContent
short_answer?: ShortAnswerContent
fill_in_blank?: FillInBlankContent
divider?: SectionDividerContent
key_fact?: KeyFactContent
```

---

## Step 2 — Add new components to `src/lib/registry.ts`

Add the following entries to `componentRegistry`. Group placement noted.

```typescript
// ── GROUP 1 — add after InterviewAnchor ─────────────────────────────────────

CalloutBlock: {
  id: 'callout-block',
  sectionField: 'callout',
  name: 'CalloutBlock',
  group: 1,
  purpose: 'Standalone highlighted callout — tip, warning, info, or exam note',
  cognitiveJob: 'Flag what matters',
  subjects: ['universal'],
  behaviourModes: ['static'],
  shadcnPrimitive: 'Alert',
  capacity: { bodyMaxWords: 60, headingMaxWords: 6 },
  printFallback: 'Bordered callout box',
  status: 'stable'
},

SummaryBlock: {
  id: 'summary-block',
  sectionField: 'summary',
  name: 'SummaryBlock',
  group: 1,
  purpose: 'Lists what this section covered — key takeaways as bullets',
  cognitiveJob: 'Consolidate and close',
  subjects: ['universal'],
  behaviourModes: ['static'],
  shadcnPrimitive: 'Card',
  capacity: { itemsMin: 2, itemsMax: 5, itemMaxWords: 25, closingMaxWords: 30 },
  printFallback: 'Bulleted list with border',
  status: 'stable'
},

SectionDivider: {
  id: 'section-divider',
  sectionField: 'divider',
  name: 'SectionDivider',
  group: 1,
  purpose: 'Named visual break between parts within a section',
  cognitiveJob: 'Signal a phase change',
  subjects: ['universal'],
  behaviourModes: ['static'],
  shadcnPrimitive: 'Separator',
  capacity: { labelMaxWords: 4 },
  printFallback: 'Horizontal rule with label',
  status: 'stable'
},

// ── GROUP 2 — add after InsightStrip ─────────────────────────────────────────

KeyFact: {
  id: 'key-fact',
  sectionField: 'key_fact',
  name: 'KeyFact',
  group: 2,
  purpose: 'Visually prominent stat, formula, or date that anchors the section',
  cognitiveJob: 'Anchor a critical fact',
  subjects: ['universal'],
  behaviourModes: ['static'],
  shadcnPrimitive: 'Card',
  capacity: { factMaxWords: 20, contextMaxWords: 30 },
  printFallback: 'Bold bordered fact box',
  status: 'stable'
},

// ── GROUP 4 — add after ReflectionPrompt ─────────────────────────────────────

StudentTextbox: {
  id: 'student-textbox',
  sectionField: 'student_textbox',
  name: 'StudentTextbox',
  group: 4,
  purpose: 'Simple write-in box for student responses — no framing beyond a prompt',
  cognitiveJob: 'Record thinking',
  subjects: ['universal'],
  behaviourModes: ['static'],
  shadcnPrimitive: 'Textarea (print: lined box)',
  capacity: { promptMaxWords: 40, linesMax: 10 },
  printFallback: 'Lined write-in area',
  status: 'stable'
},

ShortAnswerQuestion: {
  id: 'short-answer',
  sectionField: 'short_answer',
  name: 'ShortAnswerQuestion',
  group: 4,
  purpose: 'Open question with write-in space and optional mark scheme',
  cognitiveJob: 'Recall and explain in own words',
  subjects: ['universal'],
  behaviourModes: ['static'],
  shadcnPrimitive: 'Card + Collapsible (mark scheme)',
  capacity: { questionMaxWords: 60, linesMax: 10, marksMax: 10 },
  printFallback: 'Question with lined answer space, mark allocation shown',
  status: 'stable'
},

FillInTheBlank: {
  id: 'fill-in-blank',
  sectionField: 'fill_in_blank',
  name: 'FillInTheBlank',
  group: 4,
  purpose: 'Cloze passage with student-completed blanks — tests recall not recognition',
  cognitiveJob: 'Retrieve and complete',
  subjects: ['universal'],
  behaviourModes: ['static', 'hint-toggle'],
  shadcnPrimitive: 'Input inline',
  capacity: { segmentsMax: 60, blanksMax: 10, wordBankMax: 15 },
  printFallback: 'Passage with underlined blanks, word bank box below',
  status: 'stable'
},
```

---

## Step 3 — Create Svelte component files

Create these files in `src/lib/components/lectio/`.

Follow the exact same patterns as adjacent components in that folder.
Each component receives a typed `content` prop. Use shadcnPrimitive noted
above. Match the visual language of the existing components.

Files to create:
- `CalloutBlock.svelte` — renders variant-coloured alert box
- `SummaryBlock.svelte` — renders bulleted takeaway list in a card
- `SectionDivider.svelte` — renders a labelled horizontal rule
- `KeyFact.svelte` — renders a bold, visually prominent fact card
- `StudentTextbox.svelte` — renders a prompt + write-in area
- `ShortAnswerQuestion.svelte` — renders question, lines, optional collapsible mark scheme
- `FillInTheBlank.svelte` — renders prose with inline `<input>` blanks and optional word bank

Export all 7 from `src/lib/components/lectio/index.ts`.
Export all 7 from the package root `src/lib/index.ts`.

---

## Step 4 — Update Python mirror

In `backend/src/pipeline/types/section_content.py`, mirror all type
additions from Step 1 exactly. Follow the existing Pydantic patterns.

Key additions:
- `CalloutVariant` Literal type
- `CalloutBlockContent` model
- `SummaryBlockContent` + `SummaryItem` models
- `StudentTextboxContent` model
- `ShortAnswerContent` model
- `FillInBlankContent` + `FillInBlankSegment` models
- `SectionDividerContent` model
- `KeyFactContent` model
- All new fields on `SectionContent` as `Optional[X] = None`

Also update:
- `SectionHeaderContent.objective` → `objectives: Optional[list[str]] = None`
- `ExplanationCallout.type` Literal → add `'warning'` and `'exam-tip'`
- `QuizContent` → add `quiz_type: Optional[Literal['multiple-choice', 'true-false']] = None`
- `PracticeProblem` → add `problem_type: Optional[Literal['structured', 'open']] = 'structured'`

---

## Step 5 — Update `TemplateContract` interface in `src/lib/template-types.ts`

This is the most important structural change. Replace the current interface
with the version below. Read carefully — field names change.

```typescript
export interface TemplateContract {
  // ── Identity ──────────────────────────────────────────────────────────────
  id: string
  name: string
  family: TemplateFamily
  intent: LessonIntent
  tagline: string
  readingStyle: ReadingStyle
  tags: string[]

  // ── Audience and fit ──────────────────────────────────────────────────────
  bestFor: string[]
  notIdealFor: string[]
  learnerFit: LearnerFit[]
  subjects: string[]
  interactionLevel: InteractionLevel

  // ── Component contract ───────────────────────────────────────────────────
  // always_present: generator fills these in every section, no planning needed
  always_present: string[]

  // available_components: planning layer selects from this list per section
  // generator fills only what the plan selected
  available_components: string[]

  // component_budget: max times this component can appear across a whole lesson
  // omit a component to mean no cap
  component_budget: Partial<Record<string, number>>

  // defaultBehaviours: which behaviour mode to use when a component is selected
  defaultBehaviours: Partial<Record<string, BehaviourMode>>

  // ── Section role defaults ────────────────────────────────────────────────
  // When the planning layer assigns a role to a section, start from these
  // component suggestions for that role in this template.
  // Planning layer can override. Generator fills what the plan selects.
  section_role_defaults: Partial<Record<SectionRole, string[]>>

  // ── Signal affinity ──────────────────────────────────────────────────────
  // Used by planning layer to score template fit against teacher signals.
  // Keys match the signal dimensions collected in Teacher Studio.
  // Values are 0.0 (poor fit) to 1.0 (strong fit).
  signal_affinity: {
    topic_type: Partial<Record<'concept' | 'process' | 'facts' | 'mixed', number>>
    learning_outcome: Partial<Record<'understand-why' | 'be-able-to-do' | 'remember-terms' | 'apply-to-new', number>>
    class_style: Partial<Record<'tries-before-told' | 'needs-explanation-first' | 'engages-with-visuals' | 'responds-to-worked-examples' | 'restless-without-activity', number>>
    format: Partial<Record<'printed-booklet' | 'screen-based' | 'both', number>>
  }

  // ── Layout and print (render-layer only, not read by pipeline) ────────────
  layoutNotes: string[]
  responsiveRules: string[]
  printRules: string[]

  // ── Meta ──────────────────────────────────────────────────────────────────
  allowedPresets: string[]
  whyThisTemplateExists: string
  generationGuidance: TemplateGenerationGuidance
  preview: {
    subjectExample: string
    sectionTitle: string
    previewContentId: string
  }
}

// Add this new type:
export type SectionRole =
  | 'intro'
  | 'explain'
  | 'practice'
  | 'summary'
  | 'process'
  | 'compare'
  | 'timeline'
  | 'visual'
  | 'discover'
```

**Important:** Remove `lessonFlow` from the interface entirely. It is gone.
Update `template-validation.ts` — remove any reference to `lessonFlow`.
Update `scripts/export-contracts.ts` — update the exported fields to match
the new interface (add `always_present`, `available_components`,
`component_budget`, `signal_affinity`, `section_role_defaults`;
remove `lessonFlow`, `requiredComponents`, `optionalComponents`).

---

## Step 6 — Update all 12 template configs

Apply the new contract shape to every template. The changes per template:
- Remove `lessonFlow`
- Rename `requiredComponents` → `always_present` (and trim to truly structural only)
- Rename `optionalComponents` → `available_components` (and expand to include new components)
- Add `component_budget`
- Add `signal_affinity`
- Add `section_role_defaults`

Where a template name is unclear, rename it as noted below.

---

### Template 1: `guided-concept-path`
**Name change:** none — this is the baseline template, name is fine.

```typescript
always_present: [
  'section-header',
  'hook-hero',
  'explanation-block',
  'what-next-bridge'
],

available_components: [
  'definition-card',
  'worked-example-card',
  'practice-stack',
  'pitfall-alert',
  'glossary-rail',
  'diagram-block',
  'callout-block',
  'student-textbox',
  'summary-block',
  'short-answer',
  'key-fact',
  'fill-in-blank',
  'reflection-prompt',
  'section-divider'
],

component_budget: {
  'diagram-block': 2,
  'worked-example-card': 2,
  'practice-stack': 1,
  'quiz-check': 1,
  'reflection-prompt': 1
},

signal_affinity: {
  topic_type: { concept: 0.9, process: 0.5, facts: 0.6, mixed: 0.7 },
  learning_outcome: { 'understand-why': 0.9, 'be-able-to-do': 0.5, 'remember-terms': 0.6, 'apply-to-new': 0.6 },
  class_style: { 'needs-explanation-first': 0.9, 'responds-to-worked-examples': 0.8, 'engages-with-visuals': 0.5, 'restless-without-activity': 0.4, 'tries-before-told': 0.3 },
  format: { 'printed-booklet': 0.7, 'screen-based': 0.8, both: 0.7 }
},

section_role_defaults: {
  intro: ['hook-hero', 'callout-block'],
  explain: ['explanation-block', 'definition-card', 'worked-example-card'],
  practice: ['practice-stack', 'student-textbox'],
  summary: ['summary-block', 'what-next-bridge']
}
```

---

### Template 2: `guided-concept-compact`
**Name change:** rename to `concept-compact`.
Update folder name, id field, all imports, and README.

```typescript
id: 'concept-compact',
name: 'Concept Compact',

always_present: [
  'section-header',
  'hook-hero',
  'explanation-block',
  'what-next-bridge'
],

available_components: [
  'definition-card',
  'worked-example-card',
  'practice-stack',
  'pitfall-alert',
  'callout-block',
  'student-textbox',
  'summary-block',
  'short-answer',
  'section-divider'
],

component_budget: {
  'worked-example-card': 1,
  'practice-stack': 1,
  'quiz-check': 1
},

signal_affinity: {
  topic_type: { concept: 0.9, process: 0.5, facts: 0.7, mixed: 0.6 },
  learning_outcome: { 'understand-why': 0.8, 'be-able-to-do': 0.5, 'remember-terms': 0.7, 'apply-to-new': 0.5 },
  class_style: { 'needs-explanation-first': 0.9, 'responds-to-worked-examples': 0.7, 'engages-with-visuals': 0.3, 'restless-without-activity': 0.3, 'tries-before-told': 0.3 },
  format: { 'printed-booklet': 0.8, 'screen-based': 0.7, both: 0.8 }
},

section_role_defaults: {
  intro: ['hook-hero'],
  explain: ['explanation-block', 'definition-card'],
  practice: ['practice-stack'],
  summary: ['summary-block', 'what-next-bridge']
}
```

---

### Template 3: `formal-track`
**Name change:** none — intent is clear.

```typescript
always_present: [
  'section-header',
  'explanation-block',
  'what-next-bridge'
],

available_components: [
  'hook-hero',
  'definition-card',
  'worked-example-card',
  'practice-stack',
  'pitfall-alert',
  'key-fact',
  'short-answer',
  'fill-in-blank',
  'callout-block',
  'section-divider'
],

component_budget: {
  'worked-example-card': 2,
  'practice-stack': 1,
  'quiz-check': 1
},

signal_affinity: {
  topic_type: { concept: 0.7, process: 0.6, facts: 0.8, mixed: 0.5 },
  learning_outcome: { 'understand-why': 0.7, 'be-able-to-do': 0.6, 'remember-terms': 0.8, 'apply-to-new': 0.7 },
  class_style: { 'needs-explanation-first': 1.0, 'responds-to-worked-examples': 0.8, 'engages-with-visuals': 0.2, 'restless-without-activity': 0.1, 'tries-before-told': 0.2 },
  format: { 'printed-booklet': 0.9, 'screen-based': 0.6, both: 0.7 }
},

section_role_defaults: {
  intro: ['hook-hero', 'definition-card'],
  explain: ['explanation-block', 'key-fact', 'worked-example-card'],
  practice: ['practice-stack', 'short-answer'],
  summary: ['summary-block', 'what-next-bridge']
}
```

---

### Template 4: `figure-first`
**Name change:** rename to `visual-led`.
Update folder name, id field, all imports, and README.

```typescript
id: 'visual-led',
name: 'Visual Led',

always_present: [
  'section-header',
  'what-next-bridge'
],

available_components: [
  'hook-hero',
  'diagram-block',
  'diagram-compare',
  'diagram-series',
  'explanation-block',
  'definition-card',
  'practice-stack',
  'callout-block',
  'student-textbox',
  'summary-block',
  'key-fact',
  'short-answer',
  'section-divider'
],

component_budget: {
  'diagram-block': 2,
  'diagram-compare': 1,
  'diagram-series': 1,
  'practice-stack': 1
},

signal_affinity: {
  topic_type: { concept: 0.7, process: 0.6, facts: 0.5, mixed: 0.7 },
  learning_outcome: { 'understand-why': 0.8, 'be-able-to-do': 0.4, 'remember-terms': 0.5, 'apply-to-new': 0.6 },
  class_style: { 'needs-explanation-first': 0.4, 'responds-to-worked-examples': 0.4, 'engages-with-visuals': 1.0, 'restless-without-activity': 0.5, 'tries-before-told': 0.5 },
  format: { 'printed-booklet': 0.6, 'screen-based': 0.9, both: 0.7 }
},

section_role_defaults: {
  intro: ['hook-hero', 'diagram-block'],
  explain: ['diagram-block', 'explanation-block'],
  visual: ['diagram-block', 'callout-block'],
  practice: ['practice-stack', 'student-textbox'],
  summary: ['summary-block', 'what-next-bridge']
}
```

---

### Template 5: `diagram-led-lesson`
**Name change:** rename to `diagram-led`.
Update folder name, id field, all imports, and README.

```typescript
id: 'diagram-led',
name: 'Diagram Led',

always_present: [
  'section-header',
  'diagram-block',
  'what-next-bridge'
],

available_components: [
  'hook-hero',
  'explanation-block',
  'definition-card',
  'diagram-series',
  'diagram-compare',
  'worked-example-card',
  'practice-stack',
  'pitfall-alert',
  'callout-block',
  'student-textbox',
  'summary-block',
  'key-fact',
  'short-answer',
  'section-divider'
],

component_budget: {
  'diagram-block': 3,
  'diagram-series': 1,
  'diagram-compare': 1,
  'worked-example-card': 1,
  'practice-stack': 1
},

signal_affinity: {
  topic_type: { concept: 0.8, process: 0.7, facts: 0.4, mixed: 0.7 },
  learning_outcome: { 'understand-why': 0.9, 'be-able-to-do': 0.5, 'remember-terms': 0.4, 'apply-to-new': 0.6 },
  class_style: { 'needs-explanation-first': 0.5, 'responds-to-worked-examples': 0.5, 'engages-with-visuals': 1.0, 'restless-without-activity': 0.6, 'tries-before-told': 0.5 },
  format: { 'printed-booklet': 0.7, 'screen-based': 0.9, both: 0.8 }
},

section_role_defaults: {
  intro: ['hook-hero', 'diagram-block'],
  explain: ['diagram-block', 'explanation-block', 'definition-card'],
  visual: ['diagram-series', 'callout-block'],
  practice: ['practice-stack', 'student-textbox'],
  summary: ['summary-block', 'what-next-bridge']
}
```

---

### Template 6: `compare-and-apply`
**Name change:** none — intent is clear.

```typescript
always_present: [
  'section-header',
  'what-next-bridge'
],

available_components: [
  'hook-hero',
  'comparison-grid',
  'explanation-block',
  'definition-family',
  'insight-strip',
  'practice-stack',
  'pitfall-alert',
  'callout-block',
  'student-textbox',
  'summary-block',
  'short-answer',
  'fill-in-blank',
  'section-divider'
],

component_budget: {
  'comparison-grid': 1,
  'practice-stack': 1,
  'quiz-check': 1
},

signal_affinity: {
  topic_type: { concept: 0.8, process: 0.3, facts: 0.7, mixed: 0.9 },
  learning_outcome: { 'understand-why': 0.8, 'be-able-to-do': 0.5, 'remember-terms': 0.7, 'apply-to-new': 0.9 },
  class_style: { 'needs-explanation-first': 0.7, 'responds-to-worked-examples': 0.6, 'engages-with-visuals': 0.5, 'restless-without-activity': 0.5, 'tries-before-told': 0.4 },
  format: { 'printed-booklet': 0.7, 'screen-based': 0.7, both: 0.8 }
},

section_role_defaults: {
  intro: ['hook-hero', 'callout-block'],
  compare: ['comparison-grid', 'definition-family'],
  explain: ['explanation-block', 'insight-strip'],
  practice: ['practice-stack', 'short-answer'],
  summary: ['summary-block', 'what-next-bridge']
}
```

---

### Template 7: `distinction-grid`
**Name change:** rename to `classification`.
Update folder name, id field, all imports, and README.

```typescript
id: 'classification',
name: 'Classification',

always_present: [
  'section-header',
  'what-next-bridge'
],

available_components: [
  'hook-hero',
  'comparison-grid',
  'explanation-block',
  'definition-family',
  'insight-strip',
  'practice-stack',
  'pitfall-alert',
  'callout-block',
  'student-textbox',
  'summary-block',
  'short-answer',
  'fill-in-blank',
  'section-divider'
],

component_budget: {
  'comparison-grid': 1,
  'practice-stack': 1,
  'quiz-check': 1
},

signal_affinity: {
  topic_type: { concept: 0.7, process: 0.2, facts: 0.9, mixed: 0.8 },
  learning_outcome: { 'understand-why': 0.6, 'be-able-to-do': 0.4, 'remember-terms': 0.9, 'apply-to-new': 0.8 },
  class_style: { 'needs-explanation-first': 0.6, 'responds-to-worked-examples': 0.5, 'engages-with-visuals': 0.6, 'restless-without-activity': 0.5, 'tries-before-told': 0.3 },
  format: { 'printed-booklet': 0.8, 'screen-based': 0.7, both: 0.8 }
},

section_role_defaults: {
  intro: ['hook-hero'],
  compare: ['comparison-grid'],
  explain: ['explanation-block', 'definition-family'],
  practice: ['practice-stack', 'fill-in-blank'],
  summary: ['summary-block', 'what-next-bridge']
}
```

---

### Template 8: `focus-flow`
**Name change:** rename to `low-load`.
This template is the accessibility/ADHD-sensitive one. The name should
communicate its actual purpose — reduced cognitive load.
Update folder name, id field, all imports, and README.

```typescript
id: 'low-load',
name: 'Low Load',

always_present: [
  'section-header',
  'explanation-block',
  'what-next-bridge'
],

available_components: [
  'hook-hero',
  'definition-card',
  'callout-block',
  'student-textbox',
  'summary-block',
  'short-answer',
  'section-divider',
  'key-fact',
  'pitfall-alert'
],

component_budget: {
  'quiz-check': 1,
  'practice-stack': 1,
  'definition-card': 1,
  'callout-block': 2
},

signal_affinity: {
  topic_type: { concept: 0.8, process: 0.7, facts: 0.8, mixed: 0.6 },
  learning_outcome: { 'understand-why': 0.7, 'be-able-to-do': 0.7, 'remember-terms': 0.8, 'apply-to-new': 0.5 },
  class_style: { 'needs-explanation-first': 1.0, 'responds-to-worked-examples': 0.7, 'engages-with-visuals': 0.5, 'restless-without-activity': 0.4, 'tries-before-told': 0.2 },
  format: { 'printed-booklet': 0.9, 'screen-based': 0.7, both: 0.8 }
},

section_role_defaults: {
  intro: ['hook-hero', 'callout-block'],
  explain: ['explanation-block', 'key-fact'],
  practice: ['student-textbox', 'short-answer'],
  summary: ['summary-block', 'what-next-bridge']
}
```

---

### Template 9: `process-trainer`
**Name change:** rename to `procedure`.
Update folder name, id field, all imports, and README.

```typescript
id: 'procedure',
name: 'Procedure',

always_present: [
  'section-header',
  'process-steps',
  'what-next-bridge'
],

available_components: [
  'hook-hero',
  'explanation-block',
  'worked-example-card',
  'practice-stack',
  'pitfall-alert',
  'callout-block',
  'student-textbox',
  'summary-block',
  'short-answer',
  'fill-in-blank',
  'section-divider',
  'key-fact'
],

component_budget: {
  'worked-example-card': 2,
  'practice-stack': 1,
  'quiz-check': 1
},

signal_affinity: {
  topic_type: { concept: 0.3, process: 1.0, facts: 0.4, mixed: 0.5 },
  learning_outcome: { 'understand-why': 0.4, 'be-able-to-do': 1.0, 'remember-terms': 0.5, 'apply-to-new': 0.7 },
  class_style: { 'needs-explanation-first': 0.5, 'responds-to-worked-examples': 0.9, 'engages-with-visuals': 0.4, 'restless-without-activity': 0.7, 'tries-before-told': 0.5 },
  format: { 'printed-booklet': 0.9, 'screen-based': 0.7, both: 0.8 }
},

section_role_defaults: {
  intro: ['hook-hero', 'callout-block'],
  process: ['process-steps', 'key-fact'],
  explain: ['worked-example-card', 'explanation-block'],
  practice: ['practice-stack', 'student-textbox'],
  summary: ['summary-block', 'what-next-bridge']
}
```

---

### Template 10: `timeline-narrative`
**Name change:** rename to `timeline`.
Update folder name, id field, all imports, and README.

```typescript
id: 'timeline',
name: 'Timeline',

always_present: [
  'section-header',
  'timeline-block',
  'what-next-bridge'
],

available_components: [
  'hook-hero',
  'explanation-block',
  'key-fact',
  'callout-block',
  'insight-strip',
  'student-textbox',
  'summary-block',
  'short-answer',
  'section-divider',
  'pitfall-alert'
],

component_budget: {
  'timeline-block': 1,
  'insight-strip': 1,
  'quiz-check': 1
},

signal_affinity: {
  topic_type: { concept: 0.4, process: 0.7, facts: 0.8, mixed: 0.6 },
  learning_outcome: { 'understand-why': 0.7, 'be-able-to-do': 0.3, 'remember-terms': 0.8, 'apply-to-new': 0.5 },
  class_style: { 'needs-explanation-first': 0.6, 'responds-to-worked-examples': 0.3, 'engages-with-visuals': 0.8, 'restless-without-activity': 0.5, 'tries-before-told': 0.4 },
  format: { 'printed-booklet': 0.8, 'screen-based': 0.8, both: 0.9 }
},

section_role_defaults: {
  intro: ['hook-hero', 'callout-block'],
  timeline: ['timeline-block', 'key-fact'],
  explain: ['explanation-block', 'insight-strip'],
  practice: ['short-answer', 'student-textbox'],
  summary: ['summary-block', 'what-next-bridge']
}
```

---

### Template 11: `interactive-lab`
**Name change:** none — intent is clear.

```typescript
always_present: [
  'section-header',
  'simulation-block',
  'what-next-bridge'
],

available_components: [
  'hook-hero',
  'explanation-block',
  'definition-card',
  'worked-example-card',
  'practice-stack',
  'pitfall-alert',
  'diagram-block',
  'callout-block',
  'student-textbox',
  'summary-block',
  'short-answer',
  'section-divider'
],

component_budget: {
  'simulation-block': 1,
  'diagram-block': 1,
  'worked-example-card': 1,
  'practice-stack': 1
},

signal_affinity: {
  topic_type: { concept: 0.5, process: 0.6, facts: 0.3, mixed: 0.6 },
  learning_outcome: { 'understand-why': 0.8, 'be-able-to-do': 0.7, 'remember-terms': 0.3, 'apply-to-new': 0.9 },
  class_style: { 'needs-explanation-first': 0.3, 'responds-to-worked-examples': 0.5, 'engages-with-visuals': 0.8, 'restless-without-activity': 1.0, 'tries-before-told': 1.0 },
  format: { 'printed-booklet': 0.1, 'screen-based': 1.0, both: 0.4 }
},

section_role_defaults: {
  intro: ['hook-hero'],
  discover: ['simulation-block', 'callout-block'],
  explain: ['explanation-block', 'definition-card'],
  practice: ['practice-stack', 'student-textbox'],
  summary: ['summary-block', 'what-next-bridge']
}
```

---

### Template 12: `guided-discovery`
**Name change:** none — intent is clear and distinct from interactive-lab.

```typescript
always_present: [
  'section-header',
  'hook-hero',
  'explanation-block',
  'what-next-bridge'
],

available_components: [
  'simulation-block',
  'definition-card',
  'worked-example-card',
  'practice-stack',
  'pitfall-alert',
  'glossary-rail',
  'diagram-block',
  'reflection-prompt',
  'callout-block',
  'student-textbox',
  'summary-block',
  'short-answer',
  'section-divider'
],

component_budget: {
  'simulation-block': 1,
  'diagram-block': 2,
  'worked-example-card': 2,
  'practice-stack': 1,
  'reflection-prompt': 1
},

signal_affinity: {
  topic_type: { concept: 0.7, process: 0.5, facts: 0.4, mixed: 0.7 },
  learning_outcome: { 'understand-why': 0.9, 'be-able-to-do': 0.7, 'remember-terms': 0.4, 'apply-to-new': 0.8 },
  class_style: { 'needs-explanation-first': 0.8, 'responds-to-worked-examples': 0.6, 'engages-with-visuals': 0.7, 'restless-without-activity': 0.7, 'tries-before-told': 0.6 },
  format: { 'printed-booklet': 0.3, 'screen-based': 1.0, both: 0.5 }
},

section_role_defaults: {
  intro: ['hook-hero', 'callout-block'],
  explain: ['explanation-block', 'definition-card'],
  discover: ['simulation-block', 'callout-block'],
  practice: ['practice-stack', 'student-textbox'],
  summary: ['summary-block', 'reflection-prompt', 'what-next-bridge']
}
```

---

## Step 7 — Update `template-validation.ts`

Remove any logic referencing `lessonFlow`.
Replace references to `requiredComponents` with `always_present`.
Replace references to `optionalComponents` with `available_components`.
The validation function that checks preview fields should check against
`always_present` only (since only those are guaranteed to render).

---

## Step 8 — Update `scripts/export-contracts.ts`

Update the exported contract fields to match the new interface.

```typescript
// Replace the contract export mapping with:
{
  id: contract.id,
  name: contract.name,
  family: contract.family,
  intent: contract.intent,
  tagline: contract.tagline,
  reading_style: contract.readingStyle,
  tags: contract.tags,
  best_for: contract.bestFor,
  not_ideal_for: contract.notIdealFor,
  learner_fit: contract.learnerFit,
  subjects: contract.subjects,
  interaction_level: contract.interactionLevel,
  always_present: contract.always_present,
  available_components: contract.available_components,
  component_budget: contract.component_budget,
  default_behaviours: contract.defaultBehaviours,
  section_role_defaults: contract.section_role_defaults,
  signal_affinity: contract.signal_affinity,
  layout_notes: contract.layoutNotes,
  print_rules: contract.printRules,
  allowed_presets: contract.allowedPresets,
  why_this_template_exists: contract.whyThisTemplateExists,
  generation_guidance: contract.generationGuidance
}
```

After all changes, run:
```
npm run export-contracts
```

Verify output in `agents/contracts/`. Each template JSON should have
`always_present`, `available_components`, `component_budget`,
`signal_affinity`, and `section_role_defaults` fields and should NOT
have `lessonFlow`, `requiredComponents`, or `optionalComponents`.

---

## Step 9 — Update README files

For each renamed template, update `README.md` inside the template folder.
Update the template name in the heading and remove the `Lesson Flow` section.

For templates keeping the same name, remove the `Lesson Flow` section only.

---

## Step 10 — Run tests and fix breaks

Run the existing test suite. Expected breaks:

1. `template-rollout.test.ts` — any test checking `lessonFlow` or
   `requiredComponents` field names will break. Update to use new names.

2. Any test checking that `practice-stack` appears in a template's
   required list will break — it is now in `available_components`.

3. Snapshot tests on template contracts will need updating.

Fix all test breaks. Do not skip or comment them out.

---

## Rename summary

| Current ID | New ID | New Name |
|---|---|---|
| `guided-concept-compact` | `concept-compact` | Concept Compact |
| `figure-first` | `visual-led` | Visual Led |
| `diagram-led-lesson` | `diagram-led` | Diagram Led |
| `focus-flow` | `low-load` | Low Load |
| `process-trainer` | `procedure` | Procedure |
| `timeline-narrative` | `timeline` | Timeline |
| `distinction-grid` | `classification` | Classification |
| all others | unchanged | unchanged |

---

## Completion checklist

- [ ] `types.ts` — new content types added, existing types extended
- [ ] `registry.ts` — 7 new components registered
- [ ] 7 new `.svelte` component files created and exported
- [ ] `backend/.../section_content.py` — mirrored
- [ ] `template-types.ts` — new `TemplateContract` interface, `SectionRole` type
- [ ] `template-validation.ts` — updated field references
- [ ] All 12 template `config.ts` files updated
- [ ] 7 template folders renamed, imports updated everywhere
- [ ] `template-registry.ts` — imports updated for renamed templates
- [ ] `scripts/export-contracts.ts` — updated export fields
- [ ] `npm run export-contracts` — run and verified
- [ ] All tests passing

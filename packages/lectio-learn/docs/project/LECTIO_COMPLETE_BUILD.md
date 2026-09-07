# Lectio — Complete Component Build
**All components. Full schemas. Build order. Edge cases covered.**

---

## Build Order

Grouped by dependency and complexity. Build groups in order.
Within a group, order does not matter.

```
GROUP 1 — Foundation (no dependencies, pure layout)
  SectionHeader
  HookHero
  ExplanationBlock
  PrerequisiteStrip
  WhatNextBridge
  InterviewAnchor

GROUP 2 — Definition and Knowledge
  DefinitionCard
  DefinitionFamily
  GlossaryRail
  GlossaryInline
  InsightStrip

GROUP 3 — Examples and Process
  WorkedExampleCard
  ProcessSteps

GROUP 4 — Assessment and Practice
  PracticeStack
  QuizCheck
  ReflectionPrompt

GROUP 5 — Alerts and Signals
  PitfallAlert

GROUP 6 — Diagrams (needs KaTeX + SVG work)
  DiagramBlock
  DiagramCompare
  DiagramSeries

GROUP 7 — Simulation (needs iframe + InteractionSpec)
  SimulationBlock
```

---

## Complete Type Definitions

Replace the previous types.ts entirely with this.

```typescript
// src/lib/types.ts

// ─────────────────────────────────────────────
// SHARED PRIMITIVES
// ─────────────────────────────────────────────

export type Difficulty = 'warm' | 'medium' | 'cold' | 'extension'
export type GradeBand = 'primary' | 'secondary' | 'advanced'
export type HintLevel = 1 | 2 | 3
export type BehaviourMode = 'static' | 'step-reveal' | 'accordion' |
  'hint-toggle' | 'plain-formal-toggle' | 'zoom' | 'sticky' |
  'drawer' | 'inline-strip' | 'progressive-hints' | 'compare'

// ─────────────────────────────────────────────
// GROUP 1 — FOUNDATION COMPONENTS
// ─────────────────────────────────────────────

export interface SectionHeaderContent {
  title: string                    // max 12 words
  subtitle?: string                // max 20 words
  subject: string
  section_number?: string          // e.g. "Section 01"
  grade_band: GradeBand
  objective?: string               // max 30 words — learning goal
  level_pills?: LevelPill[]        // difficulty indicators
}

export interface LevelPill {
  label: string
  variant: 'all' | 'warm' | 'medium' | 'cold'
}

// ──

export type HookType = 'prose' | 'quote' | 'question' | 'data-point'

export interface HookHeroContent {
  headline: string                 // max 12 words
  body: string                     // max 80 words
  anchor: string                   // the felt need this creates
  type?: HookType                  // default: 'prose'
  // if type === 'quote'
  quote_attribution?: string
  // if type === 'question' — creates cognitive dissonance
  question_options?: string[]      // 2–3 options, no right answer revealed
  // if type === 'data-point'
  data_point?: {
    value: string                  // the striking number or fact
    label: string                  // what it means
    source?: string
  }
}

// ──

export interface ExplanationContent {
  body: string                     // max 350 words
  emphasis: string[]               // max 3 key phrases — bolded inline
}

// ──

export interface PrerequisiteItem {
  concept: string                  // max 8 words
  refresher?: string               // max 60 words — shown on tap/hover
}

export interface PrerequisiteContent {
  label?: string                   // default: "Before we begin"
  items: PrerequisiteItem[]        // max 4
}

// ──

export interface WhatNextContent {
  body: string                     // max 50 words
  next: string                     // max 15 words — concept name
  preview?: string                 // max 30 words — optional teaser
}

// ──

export interface InterviewContent {
  prompt: string                   // max 35 words — conversational question
  audience: string                 // max 10 words — who they are explaining to
  follow_up?: string               // max 25 words — a harder follow-on question
}

// ─────────────────────────────────────────────
// GROUP 2 — DEFINITION AND KNOWLEDGE
// ─────────────────────────────────────────────

export interface DefinitionContent {
  term: string
  formal: string                   // max 80 words
  plain: string                    // max 60 words
  etymology?: string
  notation?: string                // KaTeX formula — "we write this as f'(x)"
  related_terms?: string[]         // max 3 — links to glossary
  symbol?: string                  // e.g. "∂" — displayed large
}

// ──

export interface DefinitionFamilyContent {
  family_title: string             // max 10 words
  family_intro?: string            // max 40 words — why these belong together
  definitions: DefinitionContent[] // max 4
}

// ──

export interface GlossaryTerm {
  term: string
  definition: string               // max 30 words
  used_in?: string                 // sentence where term first appears
  pronunciation?: string           // e.g. "kæl-kyə-ləs"
  related?: string[]               // other terms in this glossary
}

export interface GlossaryContent {
  terms: GlossaryTerm[]            // max 8, warning at 6
}

// GlossaryInline — used inline in prose, not as a block
export interface GlossaryInlineProps {
  term: string
  definition: string               // max 30 words
}

// ──

export interface InsightCell {
  label: string                    // max 6 words
  value: string                    // max 2 lines — the key data or insight
  note?: string                    // max 20 words — supporting context
  highlight?: boolean              // visually emphasise this cell
}

export interface InsightStripContent {
  cells: InsightCell[]             // max 3, min 2
}

// ─────────────────────────────────────────────
// GROUP 3 — EXAMPLES AND PROCESS
// ─────────────────────────────────────────────

export interface WorkedStep {
  label: string                    // max 12 words — why this step
  content: string                  // max 80 words — what was done
  note?: string                    // max 30 words — aside or warning
  formula?: string                 // KaTeX for this step
  diagram_ref?: string             // id of a diagram in the section
}

export interface WorkedExampleContent {
  title: string
  setup: string                    // max 60 words
  steps: WorkedStep[]              // max 6, warning at 4
  conclusion: string               // max 40 words
  method_label?: string            // e.g. "Method A: Substitution"
  alternative?: WorkedExampleContent // optional second method to toggle
}

// ──

export interface ProcessStepItem {
  number: number
  action: string                   // max 15 words — imperative instruction
  detail: string                   // max 60 words — why, what to watch for
  input?: string                   // max 10 words — what comes in
  output?: string                  // max 10 words — what comes out
  warning?: string                 // max 20 words — common mistake here
}

export interface ProcessContent {
  title: string
  intro?: string                   // max 40 words — when to use this process
  steps: ProcessStepItem[]         // max 8
  checklist_mode?: boolean         // renders as a checklist for print
}

// ─────────────────────────────────────────────
// GROUP 4 — ASSESSMENT AND PRACTICE
// ─────────────────────────────────────────────

export interface PracticeHint {
  level: HintLevel                 // 1 = gentle, 2 = direct, 3 = near-answer
  text: string                     // max 60 words
}

export interface PracticeSolution {
  approach: string                 // max 100 words — the method
  answer: string                   // max 60 words — the result
  worked?: string                  // max 200 words — full worked version
}

export interface PracticeProblem {
  difficulty: Difficulty
  question: string                 // max 100 words
  hints: PracticeHint[]            // 1–3 hints, progressive
  solution?: PracticeSolution      // optional — not all problems need solutions
  writein_lines?: number           // 0–8 for print
  self_assess?: boolean            // learner marks own answer correct/incorrect
  context?: string                 // max 40 words — scenario framing
}

export interface PracticeContent {
  problems: PracticeProblem[]      // min 2, max 5 (was rigid tuple of 3)
  hints_visible_default?: boolean  // default false — true for scaffolded learners
  solutions_available?: boolean    // default false — true when solutions present
  label?: string                   // default "Practice Problems"
}

// ──

export interface QuizOption {
  text: string                     // max 20 words
  correct: boolean
  explanation: string              // max 40 words — why right or wrong
}

export interface QuizContent {
  question: string                 // max 60 words
  options: QuizOption[]            // 3–4 options
  feedback_correct: string         // max 30 words
  feedback_incorrect: string       // max 30 words
  show_explanations?: boolean      // default true — show per-option explanation
}

// ──

export type ReflectionType =
  'open' | 'pair-share' | 'sentence-stem' | 'timed' |
  'connect' | 'predict' | 'transfer'

export interface ReflectionContent {
  prompt: string                   // max 40 words
  type: ReflectionType
  space?: number                   // write-in lines, 0–6
  // type-specific fields
  sentence_stem?: string           // if type === 'sentence-stem'
                                   // e.g. "I used to think... but now I think..."
  time_minutes?: number            // if type === 'timed'
  pair_instruction?: string        // if type === 'pair-share'
                                   // e.g. "Discuss with the person next to you"
}

// ─────────────────────────────────────────────
// GROUP 5 — ALERTS AND SIGNALS
// ─────────────────────────────────────────────

export interface PitfallContent {
  misconception: string            // max 20 words — the specific wrong belief
  correction: string               // max 80 words — why wrong and what is true
  example?: string                 // max 40 words — misconception in action
  severity?: 'minor' | 'major'    // default 'major' — affects visual weight
}

// ─────────────────────────────────────────────
// GROUP 6 — DIAGRAMS
// ─────────────────────────────────────────────

export interface DiagramCallout {
  id: string
  x: number                        // percentage position on diagram (0–100)
  y: number
  label: string                    // max 4 words
  explanation: string              // max 40 words — revealed on tap/hover
}

export interface DiagramContent {
  svg_content: string
  caption: string                  // max 60 words
  zoom_label?: string              // max 8 words
  alt_text: string                 // accessibility — max 80 words
  callouts?: DiagramCallout[]      // max 6 numbered annotation points
  figure_number?: number           // sequential across section
}

// ──

export interface DiagramCompareContent {
  before_svg: string
  after_svg: string
  before_label: string             // max 6 words
  after_label: string              // max 6 words
  caption: string                  // max 60 words
  alt_text: string
}

// ──

export interface DiagramSeriesContent {
  title: string                    // max 10 words
  diagrams: Array<{
    svg_content: string
    step_label: string             // max 8 words
    caption: string                // max 40 words
  }>                               // max 4 diagrams
}

// ─────────────────────────────────────────────
// GROUP 7 — SIMULATION
// ─────────────────────────────────────────────

export type SimulationType =
  'graph_slider' | 'probability_tree' | 'equation_reveal' |
  'geometry_explorer' | 'molecule_viewer' | 'timeline_scrubber'

export interface InteractionSpec {
  type: SimulationType
  goal: string                     // max 40 words — what discovery this enables
  anchor_content: Record<string, unknown>  // concept-specific values
  context: {
    learner_level: string
    template_id: string
    color_mode: 'light' | 'dark'
    accent_color: string
    surface_color: string
    font_mono: string
  }
  dimensions: {
    width: string                  // e.g. "100%"
    height: number                 // px
    resizable: boolean
  }
  print_translation: 'static_midstate' | 'static_diagram' | 'hide'
}

export interface SimulationContent {
  spec: InteractionSpec
  fallback_diagram?: DiagramContent // shown if simulation cannot load
  explanation?: string              // max 60 words — what to discover
}

// ─────────────────────────────────────────────
// THE FULL SECTION OBJECT
// ─────────────────────────────────────────────

export interface SectionContent {
  section_id: string
  template_id: string

  // Required
  header: SectionHeaderContent
  hook: HookHeroContent
  explanation: ExplanationContent
  practice: PracticeContent
  what_next: WhatNextContent

  // Optional — present based on content needs
  prerequisites?: PrerequisiteContent
  definition?: DefinitionContent
  definition_family?: DefinitionFamilyContent
  worked_example?: WorkedExampleContent
  worked_examples?: WorkedExampleContent[]  // when section has multiple
  process?: ProcessContent
  diagram?: DiagramContent
  diagram_compare?: DiagramCompareContent
  diagram_series?: DiagramSeriesContent
  insight_strip?: InsightStripContent
  pitfall?: PitfallContent
  pitfalls?: PitfallContent[]     // some sections have multiple
  quiz?: QuizContent               // mid-section concept check
  reflection?: ReflectionContent
  glossary?: GlossaryContent
  simulation?: SimulationContent
  interview?: InterviewContent
}
```

---

## Complete Registry

```typescript
// src/lib/registry.ts

export interface ComponentMeta {
  id: string
  name: string
  purpose: string
  cognitiveJob: string
  subjects: string[]
  behaviourModes: BehaviourMode[]
  shadcnPrimitive: string
  capacity: Record<string, number | string>
  printFallback: string
  status: 'stable' | 'beta' | 'planned'
  group: 1 | 2 | 3 | 4 | 5 | 6 | 7
}

export const componentRegistry: Record<string, ComponentMeta> = {

  // GROUP 1 — FOUNDATION
  SectionHeader: {
    id: 'section-header', name: 'SectionHeader', group: 1,
    purpose: 'Opens a section with title, subject, objective, and level indicators',
    cognitiveJob: 'Orient the learner',
    subjects: ['universal'], behaviourModes: ['static'],
    shadcnPrimitive: 'Badge (for level pills)',
    capacity: { titleMaxWords: 12, subtitleMaxWords: 20, objectiveMaxWords: 30 },
    printFallback: 'Full static header',
    status: 'stable'
  },

  HookHero: {
    id: 'hook-hero', name: 'HookHero', group: 1,
    purpose: 'Creates felt need before explanation arrives',
    cognitiveJob: 'Create felt need',
    subjects: ['universal'], behaviourModes: ['static', 'fade-in'],
    shadcnPrimitive: 'none — pure layout',
    capacity: { headlineMaxWords: 12, bodyMaxWords: 80 },
    printFallback: 'Pull quote block with left border',
    status: 'stable'
  },

  ExplanationBlock: {
    id: 'explanation-block', name: 'ExplanationBlock', group: 1,
    purpose: 'Sustained prose that builds a mental model',
    cognitiveJob: 'Build understanding',
    subjects: ['universal'], behaviourModes: ['static'],
    shadcnPrimitive: 'Typography',
    capacity: { bodyMaxWords: 350, emphasisMax: 3 },
    printFallback: 'Static prose',
    status: 'stable'
  },

  PrerequisiteStrip: {
    id: 'prerequisite-strip', name: 'PrerequisiteStrip', group: 1,
    purpose: 'Lists assumed knowledge with optional refresher pop-ups',
    cognitiveJob: 'Activate prior knowledge',
    subjects: ['universal'], behaviourModes: ['static', 'hint-toggle'],
    shadcnPrimitive: 'Popover',
    capacity: { itemsMax: 4 },
    printFallback: 'Inline list of prerequisites',
    status: 'stable'
  },

  WhatNextBridge: {
    id: 'what-next-bridge', name: 'WhatNextBridge', group: 1,
    purpose: 'Connects the section forward to what the concept enables',
    cognitiveJob: 'Connect forward',
    subjects: ['universal'], behaviourModes: ['static'],
    shadcnPrimitive: 'Card',
    capacity: { bodyMaxWords: 50, nextMaxWords: 15, previewMaxWords: 30 },
    printFallback: 'Static, amber left rule',
    status: 'stable'
  },

  InterviewAnchor: {
    id: 'interview-anchor', name: 'InterviewAnchor', group: 1,
    purpose: 'Makes knowledge speakable — rehearse explaining the concept',
    cognitiveJob: 'Make knowledge speakable',
    subjects: ['universal'], behaviourModes: ['static'],
    shadcnPrimitive: 'Card',
    capacity: { promptMaxWords: 35, audienceMaxWords: 10, followUpMaxWords: 25 },
    printFallback: 'Static with write-in lines',
    status: 'stable'
  },

  // GROUP 2 — DEFINITION AND KNOWLEDGE
  DefinitionCard: {
    id: 'definition-card', name: 'DefinitionCard', group: 2,
    purpose: 'Anchors a formal term with formal and plain versions',
    cognitiveJob: 'Anchor formal knowledge',
    subjects: ['universal'], behaviourModes: ['static', 'plain-formal-toggle'],
    shadcnPrimitive: 'Card + Collapsible',
    capacity: { formalMaxWords: 80, plainMaxWords: 60, relatedTermsMax: 3 },
    printFallback: 'Both versions shown',
    status: 'stable'
  },

  DefinitionFamily: {
    id: 'definition-family', name: 'DefinitionFamily', group: 2,
    purpose: 'Groups related terms that belong together conceptually',
    cognitiveJob: 'Distinguish related concepts',
    subjects: ['universal'], behaviourModes: ['static', 'accordion'],
    shadcnPrimitive: 'Card + Accordion',
    capacity: { definitionsMax: 4, introMaxWords: 40 },
    printFallback: 'All definitions expanded',
    status: 'stable'
  },

  GlossaryRail: {
    id: 'glossary-rail', name: 'GlossaryRail', group: 2,
    purpose: 'Vocabulary visible in peripheral field, updates by section',
    cognitiveJob: 'Retrieve meaning without losing place',
    subjects: ['universal'], behaviourModes: ['sticky', 'drawer', 'inline-strip'],
    shadcnPrimitive: 'Card + ScrollArea + Sheet',
    capacity: { termsMax: 8, termsWarning: 6, definitionMaxWords: 30 },
    printFallback: 'Inline vocabulary strip at section end',
    status: 'stable'
  },

  GlossaryInline: {
    id: 'glossary-inline', name: 'GlossaryInline', group: 2,
    purpose: 'In-text definition pop-up on a defined term',
    cognitiveJob: 'Retrieve meaning in context',
    subjects: ['universal'], behaviourModes: ['hint-toggle'],
    shadcnPrimitive: 'Popover',
    capacity: { definitionMaxWords: 30 },
    printFallback: 'Term underlined, definition in footnote',
    status: 'stable'
  },

  InsightStrip: {
    id: 'insight-strip', name: 'InsightStrip', group: 2,
    purpose: 'Side-by-side comparison of 2–3 related values or concepts',
    cognitiveJob: 'Compare values simultaneously',
    subjects: ['universal'], behaviourModes: ['static'],
    shadcnPrimitive: 'CSS Grid',
    capacity: { cellsMax: 3, cellsMin: 2, cellLinesMax: 2 },
    printFallback: 'Static table',
    status: 'stable'
  },

  // GROUP 3 — EXAMPLES AND PROCESS
  WorkedExampleCard: {
    id: 'worked-example-card', name: 'WorkedExampleCard', group: 3,
    purpose: 'Shows reasoning in action step by step, each step justified',
    cognitiveJob: 'Watch reasoning in action',
    subjects: ['universal'], behaviourModes: ['static', 'step-reveal', 'accordion', 'compare'],
    shadcnPrimitive: 'Card + Collapsible',
    capacity: { stepsMax: 6, stepsWarning: 4, stepLabelMaxWords: 12, stepContentMaxWords: 80 },
    printFallback: 'All steps expanded',
    status: 'stable'
  },

  ProcessSteps: {
    id: 'process-steps', name: 'ProcessSteps', group: 3,
    purpose: 'A repeatable procedure where order is non-negotiable',
    cognitiveJob: 'Follow a procedure',
    subjects: ['universal'], behaviourModes: ['static', 'step-reveal'],
    shadcnPrimitive: 'Card + Separator',
    capacity: { stepsMax: 8, actionMaxWords: 15, detailMaxWords: 60 },
    printFallback: 'All steps visible, checkbox squares for print',
    status: 'stable'
  },

  // GROUP 4 — ASSESSMENT AND PRACTICE
  PracticeStack: {
    id: 'practice-stack', name: 'PracticeStack', group: 4,
    purpose: 'Problems at calibrated difficulty with progressive hints and optional solutions',
    cognitiveJob: 'Apply understanding under calibrated difficulty',
    subjects: ['universal'], behaviourModes: ['hint-toggle', 'accordion', 'progressive-hints'],
    shadcnPrimitive: 'Accordion + Collapsible',
    capacity: { problemsMin: 2, problemsMax: 5, hintsPerProblemMax: 3, questionMaxWords: 100, hintMaxWords: 60 },
    printFallback: 'All visible, write-in lines rendered',
    status: 'stable'
  },

  QuizCheck: {
    id: 'quiz-check', name: 'QuizCheck', group: 4,
    purpose: 'Quick concept check with immediate feedback mid-section',
    cognitiveJob: 'Verify understanding immediately',
    subjects: ['universal'], behaviourModes: ['static'],
    shadcnPrimitive: 'Card + Button',
    capacity: { optionsMin: 3, optionsMax: 4, questionMaxWords: 60, optionMaxWords: 20 },
    printFallback: 'Question and options shown, correct answer marked',
    status: 'stable'
  },

  ReflectionPrompt: {
    id: 'reflection-prompt', name: 'ReflectionPrompt', group: 4,
    purpose: 'Pauses forward motion and turns attention inward',
    cognitiveJob: 'Pause and consolidate',
    subjects: ['universal'], behaviourModes: ['static'],
    shadcnPrimitive: 'Card',
    capacity: { promptMaxWords: 40, spaceMax: 6 },
    printFallback: 'Prompt with write-in lines',
    status: 'stable'
  },

  // GROUP 5 — ALERTS
  PitfallAlert: {
    id: 'pitfall-alert', name: 'PitfallAlert', group: 5,
    purpose: 'Names a specific misconception before the learner makes it',
    cognitiveJob: 'Inoculate against error',
    subjects: ['universal'], behaviourModes: ['static', 'hint-toggle'],
    shadcnPrimitive: 'Alert + Collapsible',
    capacity: { misconceptionMaxWords: 20, correctionMaxWords: 80, exampleMaxWords: 40 },
    printFallback: 'Full static, amber left border',
    status: 'stable'
  },

  // GROUP 6 — DIAGRAMS
  DiagramBlock: {
    id: 'diagram-block', name: 'DiagramBlock', group: 6,
    purpose: 'Makes spatial or relational structure visible',
    cognitiveJob: 'See the structure',
    subjects: ['universal'], behaviourModes: ['static', 'zoom', 'hint-toggle'],
    shadcnPrimitive: 'Card + Dialog',
    capacity: { calloutsMax: 6, captionMaxWords: 60 },
    printFallback: 'Static SVG 80% width centred',
    status: 'stable'
  },

  DiagramCompare: {
    id: 'diagram-compare', name: 'DiagramCompare', group: 6,
    purpose: 'Before and after comparison with a drag slider',
    cognitiveJob: 'See transformation',
    subjects: ['history', 'science', 'mathematics', 'geography'],
    behaviourModes: ['compare'],
    shadcnPrimitive: 'Slider',
    capacity: { captionMaxWords: 60 },
    printFallback: 'Both diagrams shown side by side',
    status: 'stable'
  },

  DiagramSeries: {
    id: 'diagram-series', name: 'DiagramSeries', group: 6,
    purpose: 'A progression of diagrams that tells a sequence',
    cognitiveJob: 'Follow a visual progression',
    subjects: ['universal'],
    behaviourModes: ['step-reveal', 'static'],
    shadcnPrimitive: 'Tabs or step nav',
    capacity: { diagramsMax: 4 },
    printFallback: 'All diagrams in sequence with step labels',
    status: 'stable'
  },

  // GROUP 7 — SIMULATION
  SimulationBlock: {
    id: 'simulation-block', name: 'SimulationBlock', group: 7,
    purpose: 'Manipulate a variable and discover the concept through observation',
    cognitiveJob: 'Manipulate and discover',
    subjects: ['mathematics', 'physics', 'chemistry', 'statistics'],
    behaviourModes: ['static'],
    shadcnPrimitive: 'iframe sandbox',
    capacity: { onePerSection: true },
    printFallback: 'Static diagram at midstate',
    status: 'beta'
  },
}

// Helper — components ready to use (not planned)
export function getStableComponents(): ComponentMeta[] {
  return Object.values(componentRegistry)
    .filter(c => c.status === 'stable' || c.status === 'beta')
}

// Helper — components by group
export function getComponentsByGroup(group: number): ComponentMeta[] {
  return Object.values(componentRegistry).filter(c => c.group === group)
}
```

---

## Complete validate.ts

```typescript
// src/lib/validate.ts

import type { SectionContent } from './types'

function words(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length
}

function warn(location: string, message: string): string {
  return `[Lectio/${location}] ${message}`
}

export function validateSection(section: SectionContent): string[] {
  const w: string[] = []

  // Header
  if (words(section.header.title) > 12)
    w.push(warn('SectionHeader', `title exceeds 12 words`))
  if (section.header.objective && words(section.header.objective) > 30)
    w.push(warn('SectionHeader', `objective exceeds 30 words`))

  // Hook
  if (words(section.hook.headline) > 12)
    w.push(warn('HookHero', `headline exceeds 12 words`))
  if (words(section.hook.body) > 80)
    w.push(warn('HookHero', `body exceeds 80 words`))
  if (section.hook.question_options &&
      section.hook.question_options.length > 3)
    w.push(warn('HookHero', `question_options max 3`))

  // Explanation
  if (words(section.explanation.body) > 350)
    w.push(warn('ExplanationBlock', `body exceeds 350 words`))
  if (section.explanation.emphasis.length > 3)
    w.push(warn('ExplanationBlock', `emphasis max 3 items`))

  // Prerequisites
  if (section.prerequisites && section.prerequisites.items.length > 4)
    w.push(warn('PrerequisiteStrip', `items max 4`))

  // Definition
  if (section.definition) {
    if (words(section.definition.formal) > 80)
      w.push(warn('DefinitionCard', `formal exceeds 80 words`))
    if (words(section.definition.plain) > 60)
      w.push(warn('DefinitionCard', `plain exceeds 60 words`))
  }

  // Definition family
  if (section.definition_family) {
    if (section.definition_family.definitions.length > 4)
      w.push(warn('DefinitionFamily', `definitions max 4`))
  }

  // Worked example(s)
  const examples = [
    ...(section.worked_example ? [section.worked_example] : []),
    ...(section.worked_examples ?? [])
  ]
  examples.forEach((ex, ei) => {
    const label = `WorkedExampleCard[${ei}]`
    if (ex.steps.length > 6) w.push(warn(label, `steps max 6`))
    else if (ex.steps.length > 4) w.push(warn(label, `${ex.steps.length} steps — consider trimming (warning at 4)`))
    ex.steps.forEach((s, si) => {
      if (words(s.label) > 12) w.push(warn(`${label} step ${si+1}`, `label exceeds 12 words`))
      if (words(s.content) > 80) w.push(warn(`${label} step ${si+1}`, `content exceeds 80 words`))
    })
  })

  // Process
  if (section.process) {
    if (section.process.steps.length > 8)
      w.push(warn('ProcessSteps', `steps max 8`))
  }

  // Pitfall(s)
  const pitfalls = [
    ...(section.pitfall ? [section.pitfall] : []),
    ...(section.pitfalls ?? [])
  ]
  pitfalls.forEach((p, i) => {
    if (words(p.misconception) > 20)
      w.push(warn(`PitfallAlert[${i}]`, `misconception exceeds 20 words`))
    if (words(p.correction) > 80)
      w.push(warn(`PitfallAlert[${i}]`, `correction exceeds 80 words`))
  })

  // Practice
  if (section.practice.problems.length < 2)
    w.push(warn('PracticeStack', `minimum 2 problems`))
  if (section.practice.problems.length > 5)
    w.push(warn('PracticeStack', `maximum 5 problems`))
  section.practice.problems.forEach((p, i) => {
    if (words(p.question) > 100)
      w.push(warn(`PracticeStack problem ${i+1}`, `question exceeds 100 words`))
    if (p.hints.length > 3)
      w.push(warn(`PracticeStack problem ${i+1}`, `hints max 3`))
    p.hints.forEach((h, hi) => {
      if (words(h.text) > 60)
        w.push(warn(`PracticeStack problem ${i+1} hint ${hi+1}`, `hint exceeds 60 words`))
    })
  })

  // Insight strip
  if (section.insight_strip) {
    if (section.insight_strip.cells.length > 3)
      w.push(warn('InsightStrip', `cells max 3`))
    if (section.insight_strip.cells.length < 2)
      w.push(warn('InsightStrip', `cells min 2`))
  }

  // Glossary
  if (section.glossary) {
    if (section.glossary.terms.length > 8)
      w.push(warn('GlossaryRail', `terms max 8`))
    else if (section.glossary.terms.length > 6)
      w.push(warn('GlossaryRail', `${section.glossary.terms.length} terms — approaching limit (warning at 6)`))
    section.glossary.terms.forEach((t, i) => {
      if (words(t.definition) > 30)
        w.push(warn(`GlossaryRail term ${i+1}`, `definition exceeds 30 words`))
    })
  }

  // What next
  if (words(section.what_next.body) > 50)
    w.push(warn('WhatNextBridge', `body exceeds 50 words`))

  return w
}

export function warnIfInvalid(section: SectionContent): void {
  if (typeof process !== 'undefined' &&
      process.env.NODE_ENV !== 'development') return
  const warnings = validateSection(section)
  if (warnings.length === 0) return
  console.group('[Lectio] Content validation warnings')
  warnings.forEach(w => console.warn(w))
  console.groupEnd()
}
```

---

## Revised Build Order for Today

```
Hour 1 — Foundation files
  types.ts          (complete schema above)
  registry.ts       (complete registry above)
  validate.ts       (complete validator above)
  dummy-content.ts  (calculus section content)

Hour 2 — Group 1 components (all simple, no primitives needed)
  SectionHeader
  HookHero
  ExplanationBlock
  PrerequisiteStrip
  WhatNextBridge
  InterviewAnchor

Hour 3 — Group 2 + 5 (definition family + alerts)
  DefinitionCard
  DefinitionFamily
  InsightStrip
  GlossaryRail
  GlossaryInline
  PitfallAlert

Hour 4 — Group 3 + 4 (the complex ones)
  WorkedExampleCard (with step-reveal + alternative method toggle)
  ProcessSteps
  PracticeStack (with progressive hints + solution reveal)
  QuizCheck
  ReflectionPrompt

Hour 5 — Group 6 (diagrams)
  DiagramBlock (with callouts + zoom)
  DiagramCompare (slider)
  DiagramSeries (stepped)

Hour 6 — Assembly + showcase
  GuidedConceptPath template
  Component showcase page (registry-driven)
  Template showcase page
  Run and verify
```

SimulationBlock is Group 7 and depends on the
two-model interaction pipeline. Leave it for when
that pipeline is ready. Register it now, build it later.

---

## The One Principle That Governs All Components

Every component is customisable through props.
Nothing is forced. If a prop is absent, the component
renders its simplest version. If it is present,
the extended behaviour activates.

A PracticeStack with one hint per problem and no solutions
looks and feels like the simple version. A PracticeStack
with three progressive hints and full worked solutions
is the same component — just more props provided.

That is what makes this usable by anyone for any context.
> Status note (2026-03-17): This is a historical build brief. Treat `src/lib/types.ts`, `src/lib/registry.ts`, `src/lib/template-registry.ts`, and `docs/reference/component-guide.md` as the current source of truth.

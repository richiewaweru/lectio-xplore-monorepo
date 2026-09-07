# Lectio First-Class Consumption Library Proposal

## Purpose

This proposal defines the implementation plan for making **Lectio** a first-class consumption library for AI generation systems, editors, renderers, and backend validators.

The goal is to move from scattered exports and consumer-side guessing to a clean model where each Lectio component owns its own contract truth, and external systems consume a compiled contract surface.

The key principle:

```txt
Component owns truth.
Exporter aggregates truth.
Consumers use truth.
Consumers do not rewrite truth.
```

---

## 1. Problem Statement

Lectio already has strong foundations:

- typed `SectionContent`
- reusable rendering components
- component metadata
- print rules
- examples
- JSON schema exports
- generated Python/Pydantic models
- template layouts

But the current consumption surface is too fragmented.

Today, downstream systems need to understand and stitch together many files:

```txt
component-registry.json
component-field-map.json
component-schemas.json
component-examples.json
section-content-schema.json
print-rules.json
manifest.json
template JSON files
generated/python/section_content.py
```

This creates friction for Textbook Generator V3 and any future external consumer.

The current V3 issue is not that Lectio has no contract. The issue is that the contract is split across too many files, and render behavior is not expressed clearly enough for generation systems.

Example:

```json
{
  "required": ["body", "emphasis"]
}
```

This tells the consumer that `emphasis` exists. It does **not** tell the consumer that:

```txt
emphasis is a plain phrase list
phrases should appear inside body
Lectio auto-highlights those phrases
emphasis should not contain markdown
```

That behavior belongs in the component-owned contract.

---

## 2. Core Architecture Decision

### Decision

Each Lectio component should own all neutral rendering/content truth about itself.

A component should declare:

```txt
schema
metadata
print behavior
examples
content/render behavior
```

The exporter should aggregate these into one primary consumer file.

### Do not put consumer-specific logic in Lectio

Lectio must not know about:

```txt
writer
media executor
question writer
repair loop
pipeline
V3
Textbook Generator
```

Those belong to consumers.

Lectio should only expose neutral truths:

```txt
what fields exist
what each field means
how each field renders
what formatting is accepted
what constraints make the component render well
what valid examples look like
what print behavior applies
```

---

## 3. Proposed Component Folder Structure

Each first-class component should follow this structure:

```txt
src/lib/lectio/components/<component-id>/
  schema.ts
  metadata.ts
  print.ts
  examples.ts
  content-contract.ts
  module.ts
```

Example:

```txt
src/lib/lectio/components/explanation-block/
  schema.ts
  metadata.ts
  print.ts
  examples.ts
  content-contract.ts
  module.ts
```

### `module.ts`

```ts
import { componentSchema } from './schema';
import { metadata } from './metadata';
import { print } from './print';
import { examples } from './examples';
import { contentContract } from './content-contract';

export const lectioModule = {
  schema: componentSchema,
  metadata,
  print,
  examples,
  contentContract
};
```

---

## 4. New Neutral Contract Types

Add shared contract types to Lectio.

Suggested file:

```txt
src/lib/lectio/core/content-contract.ts
```

### Types

```ts
export type LectioFieldFormat =
  | 'plain_text'
  | 'plain_text_short'
  | 'plain_phrase_list'
  | 'inline_markdown'
  | 'block_markdown'
  | 'latex_raw'
  | 'media_url'
  | 'accessibility_text'
  | 'positioned_callouts'
  | 'enum'
  | 'number'
  | 'number_of_print_lines'
  | 'boolean'
  | 'structured_object'
  | 'structured_array';

export interface LectioFieldContract {
  format: LectioFieldFormat;
  description: string;
  renderBehavior?: string;
  constraints?: string[];
}

export interface LectioContentContract {
  componentId: string;
  sectionField: string | null;
  fieldContracts: Record<string, LectioFieldContract>;
  componentConstraints?: string[];
}
```

### Rules for these types

These types must stay consumer-neutral.

Allowed:

```txt
Rendered as block markdown.
Use plain phrases.
x/y are percentages from 0 to 100.
Formula should be raw LaTeX.
```

Not allowed:

```txt
The writer should repair this.
The media executor fills this.
The V3 pipeline retries this.
The question writer owns this field.
```

---

## 5. Example `content-contract.ts`

### `explanation-block/content-contract.ts`

```ts
import type { LectioContentContract } from '$lib/lectio/core/content-contract';

export const contentContract = {
  componentId: 'explanation-block',
  sectionField: 'explanation',

  fieldContracts: {
    body: {
      format: 'block_markdown',
      description: 'Main explanation text.',
      renderBehavior: 'Rendered as block markdown. Supports markdown and LaTeX math.'
    },

    emphasis: {
      format: 'plain_phrase_list',
      description: 'Phrases highlighted inside the explanation body.',
      renderBehavior: 'Lectio highlights matching phrases automatically.',
      constraints: [
        'Use plain phrases.',
        'Do not use markdown.',
        'Phrases should appear in body.',
        'Use key terms or short phrases, not full sentences.'
      ]
    },

    callouts: {
      format: 'structured_array',
      description: 'Optional callout notes displayed below the explanation.'
    }
  },

  componentConstraints: [
    'Use body for the main explanation.',
    'Use emphasis only for important repeated concepts.'
  ]
} satisfies LectioContentContract;
```

---

## 6. Components Requiring Content Contracts First

Implement `content-contract.ts` for these high-priority components first:

```txt
section-header
hook-hero
explanation-block
definition-card
key-fact
callout-block
pitfall-alert
diagram-block
worked-example-card
practice-stack
quiz-check
reflection-prompt
summary-block
what-next-bridge
process-steps
comparison-grid
timeline-block
fill-in-blank
student-textbox
short-answer
interview-anchor
prerequisite-strip
glossary-rail
definition-family
insight-strip
section-divider
diagram-compare
diagram-series
simulation-block
```

Do not include editor-only or inline-only components in the generation-facing contract for now:

```txt
image-block
video-embed
glossary-inline
```

Keep their source code. Exclude them from the main generated consumer contract.

---

## 7. Field Behavior Notes by Component

### 7.1 `explanation-block`

```txt
body:
  block_markdown

emphasis:
  plain_phrase_list
  each phrase should appear in body
  no markdown
  auto-highlighted by Lectio

callouts:
  structured_array
```

### 7.2 `practice-stack`

```txt
problems[].question:
  block_markdown

problems[].hints[].text:
  block_markdown

problems[].solution.approach:
  block_markdown

problems[].solution.answer:
  block_markdown

problems[].solution.worked:
  block_markdown

problems[].diagram:
  structured_object
  supports instructional diagram data
```

Neutral constraints:

```txt
Hint levels should be ordered from lighter support to stronger support.
Hint levels should be 1, 2, or 3.
Problem difficulty should use the supported enum.
```

### 7.3 `worked-example-card`

```txt
title:
  plain_text

setup:
  inline_markdown

steps[].label:
  plain_text_short

steps[].content:
  block_markdown

steps[].note:
  inline_markdown

steps[].formula:
  latex_raw

conclusion:
  inline_markdown

answer:
  plain_text
```

Neutral constraints:

```txt
formula should be raw LaTeX, not wrapped in $...$.
Each step should represent one reasoning move.
```

### 7.4 `quiz-check`

```txt
question:
  inline_markdown

options[].text:
  inline_markdown

options[].explanation:
  inline_markdown

feedback_correct:
  plain_text

feedback_incorrect:
  plain_text
```

Neutral constraints:

```txt
Every option needs an explanation.
Usually exactly one option should be correct unless the component explicitly supports otherwise.
Do not include option labels like A, B, C inside option text.
```

### 7.5 `definition-card`

```txt
term:
  plain_text

plain:
  inline_markdown

formal:
  inline_markdown

notation:
  latex_raw or inline_markdown depending on content

symbol:
  plain_text

examples[]:
  plain_text

related_terms[]:
  plain_text
```

Neutral constraints:

```txt
plain should be student-friendly.
formal should be more precise.
notation should be raw LaTeX when mathematical.
Do not wrap examples in quotation marks if the renderer already adds them.
```

### 7.6 `hook-hero`

```txt
headline:
  plain_text

body:
  inline_markdown for normal prose
  plain_quote_text when type is quote

anchor:
  plain_text_short

type:
  enum controlling render behavior

question_options[]:
  plain_text

data_point:
  structured_object
```

Neutral constraints:

```txt
Anchor should be a short bridge to the lesson concept.
If type is question, question_options should be present.
If type is data-point, data_point should be present.
```

### 7.7 `pitfall-alert`

```txt
misconception:
  plain_text_short

correction:
  inline_markdown

why:
  inline_markdown

example / examples[]:
  inline_markdown

severity:
  enum
```

Neutral constraints:

```txt
misconception should name the mistake briefly.
correction should directly fix the misconception.
Use examples[] consistently when multiple examples are needed.
```

### 7.8 `reflection-prompt`

```txt
prompt:
  inline_markdown

type:
  enum controlling render behavior

sentence_stem:
  plain_text, relevant when type is sentence-stem

time_minutes:
  number, relevant when type is timed

pair_instruction:
  plain_text, relevant when type is pair-share

space:
  number_of_print_lines
```

### 7.9 `what-next-bridge`

```txt
body:
  inline_markdown

next:
  plain_text_short

preview:
  plain_text

prerequisites[]:
  plain_text_short
```

### 7.10 `interview-anchor`

```txt
prompt:
  block_markdown

audience:
  plain_text_short

follow_up:
  block_markdown
```

### 7.11 `summary-block`

```txt
heading:
  plain_text

items[].text:
  inline_markdown

closing:
  inline_markdown
```

### 7.12 `process-steps`

```txt
title:
  plain_text

intro:
  inline_markdown

steps[].number:
  number

steps[].action:
  plain_text_short

steps[].detail:
  inline_markdown

steps[].input:
  plain_text_short

steps[].output:
  plain_text_short

steps[].warning:
  plain_text
```

Neutral constraints:

```txt
Step numbers should be sequential.
action should be short and verb-led.
detail explains the action.
input/output should be short labels, not paragraphs.
```

### 7.13 `fill-in-blank`

```txt
instruction:
  plain_text

segments[].text:
  plain_text

segments[].is_blank:
  boolean controlling blank rendering

segments[].answer:
  plain_text, required when is_blank is true

word_bank[]:
  plain_text
```

Neutral constraints:

```txt
Use alternating text and blank segments.
Every blank segment should have an answer.
If word_bank exists, it should include the blank answers.
```

### 7.14 `diagram-block`

```txt
image_url:
  media_url

caption:
  plain_text

alt_text:
  accessibility_text

zoom_label:
  plain_text_short

figure_number:
  number

callouts:
  positioned_callouts
```

Neutral constraints:

```txt
Callout x and y values are percentages from 0 to 100.
Callout labels should be short.
Callout explanations should clarify the labeled part.
Callouts may apply to image-based diagrams.
```

Important renderer follow-up:

```txt
DiagramBlock should support callouts over image_url, not only SVG.
```

### 7.15 `comparison-grid`

```txt
title:
  plain_text

intro:
  plain_text

columns[].id:
  plain_text_short

columns[].title:
  plain_text_short

columns[].summary:
  plain_text

columns[].detail:
  plain_text

rows[].criterion:
  plain_text_short

rows[].values[]:
  plain_text

rows[].takeaway:
  plain_text_short

apply_prompt:
  plain_text
```

Neutral constraints:

```txt
Each row.values length should match columns.length.
Column ids should be stable short ids.
```

### 7.16 `timeline-block`

```txt
title:
  plain_text

intro:
  plain_text

events[].year:
  plain_text_short

events[].title:
  plain_text

events[].summary:
  plain_text

events[].impact:
  plain_text

events[].tags[]:
  plain_text_short

closing_takeaway:
  plain_text
```

Neutral constraints:

```txt
Events should usually be chronological.
Each event should have a stable id.
year can be a date, era, or sequence label.
```

---

## 8. Diagram Callout Decision

Do **not** remove callouts from `diagram-block`.

Even if SVG generation is retired for now, images may still need labels and callouts.

Current callout shape already works conceptually:

```json
{
  "id": "leaf",
  "x": 35,
  "y": 42,
  "label": "Leaf",
  "explanation": "This is where most photosynthesis happens."
}
```

The renderer should be updated later so callouts can appear over `image_url` diagrams too.

---

## 9. Guided Concept Path Update

The actual `guided-concept-path` layout already behaves as a flexible renderer. It conditionally renders many `SectionContent` fields.

Therefore, the generation-facing config should stop treating it as a strict required-component template.

Update guided concept config:

```ts
always_present: [],
contextually_present: [],
available_components: AGENT_SUPPORTED_COMPONENT_IDS,
component_budget: {},
max_per_section: {}
```

Optional soft limits may remain if needed:

```ts
component_budget: {
  'diagram-block': 3,
  'diagram-series': 2,
  'simulation-block': 1
},
max_per_section: {
  'practice-stack': 1,
  'quiz-check': 1,
  'reflection-prompt': 1
}
```

Principle:

```txt
Blueprint decides what appears.
Template renders whatever valid fields exist.
Validator ensures fields are valid.
```

---

## 10. Export Contract Proposal

Add a new primary export:

```txt
contracts/lectio-content-contract.json
```

This becomes the main file consumed by external systems.

### Shape

```json
{
  "version": "1.0.0",
  "source": "lectio",
  "default_template_id": "guided-concept-path",
  "formatting_policy": {},
  "templates": {},
  "planner_index": {},
  "component_cards": {},
  "excluded_components": {}
}
```

### Include in each component card

```txt
component_id
section_field
role
cognitive_job
subjects
capacity
capabilities
status
schema summary
field contracts
component constraints
examples
print behavior
```

### Formatting policy

```json
{
  "default": "plain_text unless field contract says otherwise",
  "inline_markdown": "Supports bold, italic, inline code, and inline math using $...$.",
  "block_markdown": "Supports paragraphs, lists, bold, italic, and math using $...$ or $$...$$.",
  "latex_raw": "Raw LaTeX only. Do not wrap in $...$ unless field contract says markdown math.",
  "plain_phrase_list": "Plain phrases, no markdown. Usually used for matching/highlighting.",
  "positioned_callouts": "Labels positioned using x/y percentages from 0 to 100."
}
```

---

## 11. Export Cleanup Plan

### Keep as primary exports

```txt
contracts/lectio-content-contract.json
generated/python/section_content.py
contracts/section-content-schema.json
```

### Demote or delete after migration

These should no longer be first-class standalone consumer exports after Textbook Generator moves to the new contract:

```txt
component-field-map.json
component-registry.json
component-schemas.json
component-examples.json
manifest.json
print-rules.json
preset-registry.json
individual template JSON files
```

They may exist temporarily during migration, but the final public consumption surface should be much smaller.

---

## 12. Template Export Policy

For now, only export these templates in the main content contract:

```txt
guided-concept-path
open-canvas
```

The other templates may remain in source code but should not be part of the primary generation-facing export until they are high quality and actively supported.

---

## 13. Excluded Components for Current Contract

Exclude these from the main content contract for now:

```txt
image-block
video-embed
glossary-inline
```

Reason:

```txt
image-block:
  teacher/editor-attached image component

video-embed:
  teacher/editor-attached video component

glossary-inline:
  inline helper, not standalone SectionContent block
```

Do not delete their source code.

---

## 14. Exporter Implementation Plan

### Add export policy

Suggested file:

```txt
src/lib/lectio/export-policy.ts
```

```ts
export const CONTENT_CONTRACT_TEMPLATE_IDS = [
  'guided-concept-path',
  'open-canvas'
] as const;

export const CONTENT_CONTRACT_EXCLUDED_COMPONENT_IDS = [
  'image-block',
  'video-embed',
  'glossary-inline'
] as const;
```

### Add contract builder

Suggested file:

```txt
src/lib/lectio/build-content-contract.ts
```

Responsibilities:

```txt
load component modules
filter excluded components
require contentContract for included components
combine metadata + schema summary + contentContract + examples + print
build planner_index
include selected template summaries
write lectio-content-contract.json
```

Pseudo-code:

```ts
export function buildLectioContentContract() {
  const componentCards = lectioComponentModules
    .filter((module) => module.metadata.sectionField !== null)
    .filter((module) => !CONTENT_CONTRACT_EXCLUDED_COMPONENT_IDS.includes(module.metadata.id as any))
    .map((module) => buildComponentCard(module));

  return {
    version: '1.0.0',
    source: 'lectio',
    default_template_id: 'guided-concept-path',
    formatting_policy: buildFormattingPolicy(),
    templates: buildTemplateSummaries(componentCards),
    planner_index: buildPlannerIndex(componentCards),
    component_cards: Object.fromEntries(
      componentCards.map((card) => [card.component_id, card])
    ),
    excluded_components: buildExcludedComponentSummary()
  };
}
```

### Update export script

Update:

```txt
scripts/export-contracts.ts
```

Add output:

```txt
contracts/lectio-content-contract.json
```

Keep:

```txt
contracts/section-content-schema.json
generated/python/section_content.py
```

Demote old fragmented exports after consumer migration.

---

## 15. Validation Plan

### Lectio validation

Lectio exporter should validate:

- [ ] every exported component has `contentContract`
- [ ] `contentContract.componentId` matches metadata id
- [ ] `contentContract.sectionField` matches metadata sectionField
- [ ] every `fieldContracts` path refers to a known schema path where feasible
- [ ] examples validate against component schema
- [ ] exported components exclude configured excluded ids
- [ ] exported templates are only selected ids

### Consumer validation

Consumers such as Textbook Generator should validate:

- [ ] generated section validates against generated Pydantic models
- [ ] field-level semantic checks pass where needed
- [ ] invalid fields do not reach `document_json`
- [ ] repair/retry logic remains consumer-owned

Semantic checks that belong to the consumer:

```txt
explanation.emphasis phrases appear in explanation.body
comparison_grid row values match columns length
fill_in_blank blank segments have answers
practice hint levels are ordered
quiz has acceptable correct answer count
```

---

## 16. Textbook Generator V3 Consumption Plan

V3 should stop treating `manifest_components` as the main writer guidance.

New flow:

```txt
Lectio content contract
   |
   ├── planner_index -> architect/planner
   ├── templates -> blueprint constraints
   └── component_cards -> section writers/media/question systems

Generated Python models
   |
   └── strict backend validation
```

### V3 updates

- [ ] Load `lectio-content-contract.json`.
- [ ] Replace manifest lookup with component card lookup.
- [ ] Architect uses planner-facing metadata:
  - role
  - cognitive job
  - phase
  - capabilities
  - capacity
  - template availability
- [ ] Writer receives selected component cards plus section intent.
- [ ] Media systems read neutral field contracts but decide generation strategy themselves.
- [ ] Pydantic validates field payloads before assembly.
- [ ] Consumer repair loop remains outside Lectio.

---

## 17. Implementation Checklist

### Phase 1 — Contract Types

- [ ] Add `src/lib/lectio/core/content-contract.ts`.
- [ ] Define `LectioFieldFormat`.
- [ ] Define `LectioFieldContract`.
- [ ] Define `LectioContentContract`.
- [ ] Ensure naming is consumer-neutral.

Done when:

```txt
Types compile.
No writer/media/repair/pipeline terms appear in Lectio contract types.
```

---

### Phase 2 — Component Contracts

- [ ] Add `content-contract.ts` to high-priority components.
- [ ] Update each component `module.ts` to export `contentContract`.
- [ ] Make all included modules satisfy the shared type.
- [ ] Exclude editor-only or inline-only components from generated contract.

Done when:

```txt
Each exported component has schema, metadata, print, examples, and contentContract.
```

---

### Phase 3 — Guided Concept Config

- [ ] Update guided-concept generation-facing contract.
- [ ] Remove required `always_present` assumptions.
- [ ] Allow all supported exported components.
- [ ] Keep layout flexible.

Done when:

```txt
guided-concept-path no longer forces required components in the generation-facing export.
```

---

### Phase 4 — Content Contract Exporter

- [ ] Add export policy.
- [ ] Add `buildLectioContentContract()`.
- [ ] Build component cards from modules.
- [ ] Build planner index.
- [ ] Build template summaries.
- [ ] Include formatting policy.
- [ ] Write `contracts/lectio-content-contract.json`.

Done when:

```txt
npm run export-contracts creates lectio-content-contract.json.
The file contains selected templates, component cards, planner index, and formatting policy.
```

---

### Phase 5 — Export Cleanup

- [ ] Keep `section-content-schema.json`.
- [ ] Keep `generated/python/section_content.py`.
- [ ] Keep old exports temporarily if Textbook Generator still depends on them.
- [ ] Remove or demote old fragmented exports after migration.
- [ ] Update docs.

Done when:

```txt
The recommended public consumption path is lectio-content-contract.json + generated Python models.
```

---

### Phase 6 — Diagram Callouts

- [ ] Keep callouts in `diagram-block` contract.
- [ ] Define callouts as positioned labels.
- [ ] Update `DiagramBlock.svelte` later to display callouts over `image_url` diagrams.
- [ ] Keep SVG support in Lectio source, but do not require V3 to generate SVG.

Done when:

```txt
Diagram callouts are not removed and are documented as image-compatible positioned labels.
```

---

### Phase 7 — V3 Migration

- [ ] Load `lectio-content-contract.json` in Textbook Generator.
- [ ] Replace manifest use with component cards.
- [ ] Feed planner metadata to architect.
- [ ] Feed field contracts to writers.
- [ ] Validate output with generated Pydantic models.
- [ ] Keep repair behavior inside Textbook Generator.

Done when:

```txt
V3 no longer needs component-registry + field-map + examples + schema stitched manually.
Writer receives selected component cards.
Invalid component payloads are blocked before document_json.
```

---

## 18. Acceptance Criteria

The implementation is complete when:

- [ ] Lectio components are self-describing.
- [ ] A new component can be added by creating schema, metadata, print, examples, and content-contract files.
- [ ] `npm run export-contracts` produces `lectio-content-contract.json`.
- [ ] The new contract contains enough planner-facing and render-facing information for consumers.
- [ ] The new contract does not include consumer-specific terms.
- [ ] Guided Concept Path is treated as a flexible renderer.
- [ ] Only selected templates are exported in the main consumer contract.
- [ ] Editor-only components are excluded from the main consumer contract.
- [ ] Pydantic export remains available for backend validation.
- [ ] Textbook Generator can consume one primary contract instead of multiple fragmented files.

---

## 19. Final Direction

Lectio should become a library where a component is not only a Svelte renderer.

A first-class Lectio component should declare:

```txt
what it renders
what fields it needs
what each field means
how each field behaves
how it prints
what valid examples look like
how it can be safely consumed
```

The exporter then turns those component-owned truths into a single clean contract for consumers.

This makes Lectio stronger as:

```txt
UI component library
AI generation contract layer
lesson editor foundation
backend validation source
external consumption package
```

The final architecture:

```txt
Component source truth
   -> compiled Lectio content contract
      -> consumers plan/write/render/validate safely
```

---

## 20. Follow-up Mini Proposal: Make Behavior Truly Component-Owned

### Current status

The recent Lectio implementation correctly added the unified export structure:

```txt
contracts/lectio-content-contract.json
contracts/section-content-schema.json
generated/python/section_content.py
```

It also added the right architecture pieces:

```txt
content-contract.ts type definitions
build-content-contract.ts aggregator
export-policy.ts
module validation
component_cards
planner_index
formatting_policy
```

This is the right direction.

However, the current component contracts are still too shallow. Many components currently define behavior like this:

```ts
fieldContracts: {
  content: {
    format: 'structured_object',
    description: 'Schema-aligned content payload for this component.'
  }
}
```

That proves the component has a contract file, but it does not yet describe how the component actually renders its fields.

The desired state is not:

```txt
build-content-contract.ts figures out behavior centrally
```

The desired state is:

```txt
each component owns its own behavior
build-content-contract.ts only aggregates it
```

---

### Core correction

`build-content-contract.ts` should not become a second source of truth.

Its job should be only:

```txt
read component modules
filter exportable components
validate module completeness
aggregate component-owned contracts
write lectio-content-contract.json
```

It should not decide:

```txt
which fields use markdown
which fields use raw LaTeX
which fields are plain phrases
which fields behave as positioned callouts
which fields must match other fields
```

Those rules belong in each component's `content-contract.ts`.

---

### Correct ownership model

```txt
Component folder owns behavior
        |
        v
module.ts exposes behavior
        |
        v
build-content-contract.ts aggregates behavior
        |
        v
lectio-content-contract.json exports behavior
        |
        v
consumers use behavior
```

Expanded:

```txt
explanation-block/
  schema.ts              -> data shape
  metadata.ts            -> planner-facing role/capacity
  print.ts               -> print behavior
  examples.ts            -> valid examples
  content-contract.ts    -> field render behavior
  module.ts              -> component-owned bundle

build-content-contract.ts
  -> reads the bundle
  -> does not invent behavior
```

---

### Desired `content-contract.ts` standard

Every generation-facing component should define field-level behavior using actual schema paths.

Bad placeholder:

```ts
fieldContracts: {
  content: {
    format: 'structured_object',
    description: 'Schema-aligned content payload for this component.'
  }
}
```

Good component-owned contract:

```ts
fieldContracts: {
  body: {
    format: 'block_markdown',
    description: 'Main explanation text.',
    renderBehavior: 'Rendered as block markdown. Supports markdown and LaTeX math.'
  },
  emphasis: {
    format: 'plain_phrase_list',
    description: 'Phrases highlighted inside the explanation body.',
    renderBehavior: 'Lectio highlights matching phrases automatically.',
    constraints: [
      'Use plain phrases.',
      'Do not use markdown.',
      'Phrases should appear in body.',
      'Use key terms or short phrases, not full sentences.'
    ]
  },
  callouts: {
    format: 'structured_array',
    description: 'Optional callout notes displayed with the explanation.'
  }
}
```

The rule:

```txt
No generic `content: structured_object` for stable generation-facing components.
```

A generic fallback may be allowed only for:

```txt
planned components
non-generation components
temporary migration files explicitly marked as incomplete
```

---

### Component behavior should stay neutral

The component contract should remain consumer-neutral.

Allowed in Lectio:

```txt
Rendered as block markdown.
Formula should be raw LaTeX.
Values should be plain phrases.
Callout x/y values are percentages from 0 to 100.
Rows should align with columns.
```

Not allowed in Lectio:

```txt
The writer fills this.
The media executor fills this.
The repair loop should retry this.
V3 should do this.
Question writer owns this.
```

Consumer strategy belongs downstream.

Lectio exports render/content truth only.

---

### Priority components to fix

Replace placeholder content contracts first for:

```txt
explanation-block
practice-stack
worked-example-card
quiz-check
definition-card
hook-hero
pitfall-alert
reflection-prompt
what-next-bridge
summary-block
process-steps
fill-in-blank
diagram-block
comparison-grid
timeline-block
interview-anchor
section-header
key-fact
callout-block
student-textbox
short-answer
```

Then continue with:

```txt
prerequisite-strip
definition-family
glossary-rail
insight-strip
section-divider
diagram-compare
diagram-series
simulation-block
```

Excluded for now:

```txt
image-block
video-embed
glossary-inline
```

These should remain in source, but not in the main generation-facing content contract.

---

### Minimum field behavior expectations by component

#### `explanation-block`

```txt
body -> block_markdown
emphasis -> plain_phrase_list
callouts -> structured_array
```

#### `practice-stack`

```txt
problems[].question -> block_markdown
problems[].hints[].text -> block_markdown
problems[].solution.approach -> block_markdown
problems[].solution.answer -> block_markdown
problems[].solution.worked -> block_markdown
problems[].diagram -> structured_object
```

#### `worked-example-card`

```txt
title -> plain_text
setup -> inline_markdown
steps[].label -> plain_text_short
steps[].content -> block_markdown
steps[].note -> inline_markdown
steps[].formula -> latex_raw
conclusion -> inline_markdown
answer -> plain_text
```

#### `quiz-check`

```txt
question -> inline_markdown
options[].text -> inline_markdown
options[].explanation -> inline_markdown
feedback_correct -> plain_text
feedback_incorrect -> plain_text
```

#### `definition-card`

```txt
term -> plain_text
plain -> inline_markdown
formal -> inline_markdown
notation -> latex_raw or inline_markdown depending on content
symbol -> plain_text
examples[] -> plain_text
related_terms[] -> plain_text
```

#### `hook-hero`

```txt
headline -> plain_text
body -> inline_markdown or plain_quote_text depending on type
anchor -> plain_text_short
type -> enum
question_options[] -> plain_text
data_point -> structured_object
```

#### `diagram-block`

```txt
image_url -> media_url
caption -> plain_text
alt_text -> accessibility_text
zoom_label -> plain_text_short
figure_number -> number
callouts -> positioned_callouts
```

Important:

```txt
Keep callouts.
Callouts are part of the component truth.
They should be compatible with image-based diagrams.
```

#### `comparison-grid`

```txt
title -> plain_text
intro -> plain_text
columns[].id -> plain_text_short
columns[].title -> plain_text_short
columns[].summary -> plain_text
columns[].detail -> plain_text
rows[].criterion -> plain_text_short
rows[].values[] -> plain_text
rows[].takeaway -> plain_text_short
apply_prompt -> plain_text
```

Constraint:

```txt
Each row.values length should match columns.length.
```

#### `fill-in-blank`

```txt
instruction -> plain_text
segments[].text -> plain_text
segments[].is_blank -> boolean
segments[].answer -> plain_text
word_bank[] -> plain_text
```

Constraint:

```txt
Every blank segment should have an answer.
```

---

### Exporter validation improvements

The exporter currently validates that content contracts exist and match component IDs/section fields.

That is good but not enough.

Add stricter validation:

- [ ] Fail if an eligible stable component only has `content: structured_object`.
- [ ] Warn or fail if field contract keys do not correspond to known schema fields or nested paths.
- [ ] Fail if `componentId` does not match metadata id.
- [ ] Fail if `sectionField` does not match metadata section field.
- [ ] Fail if examples do not validate against the component schema.
- [ ] Warn if a component uses known markdown-rendered fields but has no markdown field contract.
- [ ] Warn if diagram-like components omit `caption` or `alt_text` behavior.
- [ ] Warn if callout-bearing components omit callout behavior.

This ensures the exporter does not merely check for contract presence. It checks contract usefulness.

---

### `build-content-contract.ts` target behavior

`build-content-contract.ts` should remain simple.

It should:

```txt
include contentContract.fieldContracts exactly as authored by the component
include metadata exactly from the component
include examples exactly from the component
include print behavior exactly from the component
include schema summary from SectionContent schema
include selected template summaries
include planner index
include excluded component summary
```

It should not:

```txt
invent field behavior
rewrite component constraints
add V3-specific strategy
add repair hints
assign fields to writers/media/question systems
```

---

### Completion checklist for this follow-up pass

- [ ] Every exported component owns a real `content-contract.ts`.
- [ ] No stable generation-facing component uses only generic `content: structured_object`.
- [ ] `build-content-contract.ts` only aggregates component-owned data.
- [ ] Export validation fails on placeholder contracts for stable components.
- [ ] `lectio-content-contract.json` exposes detailed field-level behavior.
- [ ] `diagram-block` keeps callouts and describes image-compatible positioned callouts.
- [ ] No consumer-specific terms leak into Lectio contracts.
- [ ] Docs state that content behavior belongs in component-owned `content-contract.ts`.
- [ ] Builder docs show the required component folder shape:

```txt
schema.ts
metadata.ts
print.ts
examples.ts
content-contract.ts
module.ts
```

---

### Final desired state

The desired state is:

```txt
A builder creates a component.
The component declares everything needed to render well.
The exporter aggregates that truth.
Consumers receive a clean contract.
Consumers do not guess component behavior.
```

This makes Lectio a serious first-class consumption library.

The final boundary stays clean:

```txt
Lectio:
  neutral content/render contract

Textbook Generator:
  generation strategy, validation policy, repair/retry, and orchestration
```


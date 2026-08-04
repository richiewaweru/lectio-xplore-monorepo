# Prompt for ChatGPT

You are helping architect a ground-up rework of an educational content library. Read everything below, then produce the artifacts listed in §8. Ask clarifying questions only if something is genuinely ambiguous — otherwise make a decisive call and note the assumption.

---

## 1. The product

**Lectio** is a published NPM library (SvelteKit / Svelte 5 / TypeScript). It owns the content contract, the rendering components, the component registry, and the print stylesheet for an AI textbook generation platform.

**The textbook agent** is the consuming app: a teacher-facing tool that generates differentiated printed booklets. Teachers describe learner groups in plain language; the system generates a per-group booklet. Teachers review and approve; **students receive printed books and have no screen time at all.**

Stack: FastAPI + Python backend on Railway, SvelteKit frontend on Vercel, PostgreSQL, PDF export through headless Chromium via Playwright. Generation runs through a multi-node pipeline (planner → section writers → visual generation → QC/coherence review), streamed over SSE with a document snapshot in PostgreSQL as the source of truth.

Scale: concierge pilot. A handful of teachers, not self-serve. Solutions must match that — no durable job queues, no worker infrastructure, no multi-provider fallbacks. Simplest thing that works.

### The governing fact

**The printed booklet is the product.** The screen view is a review surface for the teacher, nothing more. Every design decision follows from this.

---

## 2. The problem

Print quality has been the founder's single biggest unsolved pain. Components were built screen-first and print was retrofitted. The result reads as a website that was printed, not a book that was designed.

These findings were verified directly against the codebase:

### 2.1 Print is a subtraction layer

`src/lib/styles/print-theme.css` is roughly 400 lines, overwhelmingly of the form:

```css
background: white !important;
border: none !important;
border-radius: 2px !important;
box-shadow: none !important;
display: none !important;
```

Every rule undoes a screen decision. Nothing in the pipeline ever makes a *page* decision. The ceiling of subtraction is "not ugly."

### 2.2 Two competing print strategies

Four components branch on `usePrintMode()` and emit entirely different markup (GlossaryRail, WhatNextBridge, SimulationBlock, DefinitionFamily). The rest are simply overridden by CSS. Two mental models, unpredictable output.

### 2.3 Builder chrome reaches the printed page

Confirmed in exported PDFs: the app wordmark and user avatar; a keyboard-shortcuts hint bar; QC issue counts (`⚠ 3`); carousel navigation (`< Previous  Frame 1  Frame 2  Next >`); empty radio circles beside quiz options; the placeholder text `Write your answer here…`; unrendered LaTeX (`$CO_2 + H_2O \RIGHTARROW ...$`); internal step metadata letter-spaced into illegibility (`I N PUT : C H E M I CAL F O R M UL AS`).

Worst of all, **component names print as labels above content**: `DIAGRAM`, `EXPLANATION`, `DEFINE`, `PROCESS`, `SERIES`, `QUIZ`. No textbook prints the word "EXPLANATION" above a paragraph. These are editor affordances that escaped onto a student's page.

Section titles also print twice — once as a small breadcrumb, then again as a large display heading.

### 2.4 Space is wasted structurally

1. `[data-lectio-block='section-header'] { break-before: page }` — **every section starts a new page.** A three-paragraph section eats a full sheet.
2. `[data-print-container='atomic'] { break-inside: avoid }` applied broadly — a block at 60% of page height jumps to the next page and orphans the remainder.
3. Everything is a full-width row. A one-sentence definition occupies the same horizontal strip as a 350-word explanation.
4. Measure is ~100+ characters per line. Textbooks sit at 65–75.
5. Every block is a `Card` with border, background, rounded corners and shadow. When everything is emphasised, nothing is.

### 2.5 Missing fundamentals

No `orphans`, no `widows`, no `hyphens`, no serif/print type treatment, no page numbers on the builder export path. Page geometry (`@page` size and margins) lives in the **consuming app**, not in the library — so the library does not own its own page.

### 2.6 The schema already disagrees with itself

There are two document shapes and a lossy converter between them:

```
SectionContent (generation format)      LessonDocument (builder format)
src/lib/schema/types.ts                 src/lib/teacher/document.ts
──────────────────────────              ──────────────────────────
wide record, 33 named fields            ordered array of blocks
one of each                             repeatable
order = hardcoded array                 order = position field
```

Bridged by `fromSectionContents` / `toSectionContents`. Three confirmed losses:

- **Teacher ordering is destroyed.** `toSectionContents` builds an empty shell and drops blocks in by field name. Order is re-derived from `BLOCK_FIELD_ORDER`, a hardcoded array in the library. If a teacher moves a diagram above an explanation, the order snaps back.
- **Repeats are dropped.** `applyBlockToSection` keeps the first `simulation-block` and discards the rest. There is a test asserting this. Two explanations in a section is unrepresentable.
- **Plural escape hatches exist only to survive this**: `worked_examples[]` and `pitfalls[]` sit alongside their singular forms and are special-cased in both directions.

This violates two of the product's stated principles — *no silent veto power* and *teacher edits are sacred* — structurally, at the format level.

---

## 3. The key insight: the pipeline is already half-way there

The generation pipeline already separates what a block *is* from what it *means*. The blueprint emits:

```python
"components": [{"component_id": "explanation-card", "intent": "Explain"}]
```

And the section-writer prompt builder already takes intent as a separate argument:

```python
format_component_contract_for_writer(card, content_intent)
```

Object and intent are already distinct fields. They then get collapsed into a single named slot at the last step.

### Where it collapses

```
Lectio contracts (exported JSON, read via LECTIO_CONTRACTS_DIR env var)
    │  get_planner_index / get_component_card / get_template_contract
    ▼
planner palette prompt          _planner_index_block()
    │  emits "cid [section_field]: role - cognitive_job" + budgets + limits
    ▼
blueprint                       components: [{component_id, intent}]   ← still separate
    │
    ▼
section brief → writer prompt   component card + content_intent + schema shape
    │
    ▼
component_ready event           {component_id, section_id, position, section_field, data}
    │                                                     ▲
    │                                                     └── position IS carried
    ▼
merge_stream_event              document_json[sections][i][section_field] = data
                                                           ▲
                                                           └── position is DISCARDED
```

The event carries `position`. The merge throws it away because the destination is a wide record with named slots. This is the **same failure** as `BLOCK_FIELD_ORDER` on the builder side — two independent places where ordering dies, for the same reason.

**The fix is to make the destination an ordered array.**

Crucially: the backend reads Lectio's exported contracts from a directory set by an environment variable (`LECTIO_CONTRACTS_DIR`). The seam between the two systems is already a config value. Changing the exported vocabulary changes the pipeline's reasoning largely by data, not code.

---

## 4. The proposed model

### 4.1 Invert the layering

```
CURRENT                          PROPOSED
──────────────────               ──────────────────
screen component                 page object (built for paper)
      │                                │
   strip for print               add decoration for screen
      │                                │
compromised page                 clean page, adequate screen
```

A page-first design reads acceptably in a browser. A screen-first design never reads well on paper. That asymmetry is the whole argument.

### 4.2 Separate object from intent

Currently fused. `PitfallAlert` is simultaneously *a box on the page* and *a warning about a misconception*. Because they are fused, every new teaching move requires a new component — which is how the library reached 33 fields.

- **object** — what it is on the page. Determines layout, fragmentation, print behaviour. ~10 of these. Stable indefinitely.
- **intent** — what it means pedagogically. Determines emphasis, generation prompt, QC rules, palette label. Grows freely at zero render cost.

```
pitfall   → { object: 'aside', intent: 'warn' }
key_fact  → { object: 'aside', intent: 'emphasise' }
callout   → { object: 'aside', intent: 'note' }
```

Same renderer, different meaning. Adding a teaching move becomes adding a string to an enum.

### 4.3 Target schema (draft — refine it)

```ts
interface Section {
  id: string;
  title: string;
  blocks: Block[];          // ordered, repeatable, heterogeneous
}

type PageObject =
  | 'heading' | 'prose' | 'list' | 'table' | 'figure'
  | 'aside' | 'worked-example' | 'questions' | 'choices' | 'answer-key';

interface Block {
  id: string;
  object: PageObject;
  intent: Intent;           // open enum, grows freely
  content: ObjectContent;   // shape keyed off `object`, not `intent`
}
```

What disappears: `BLOCK_FIELD_ORDER`, `fromSectionContents`, `toSectionContents`, `applyBlockToSection`, `emptySectionShell`, the plural hacks, and most of `print-theme.css`. One format for generation and for the builder.

### 4.4 Field mapping — 33 current fields into 10 objects

| Object | Absorbs |
|---|---|
| Heading | `header`, `divider` |
| Prose | `explanation`, `hook`, `definition`, `what_next` |
| List | `process`, `summary`, `prerequisites`, `glossary` |
| Table | `definition_family`, `comparison_grid`, `insight_strip`, `timeline` |
| Figure | `diagram`, `image_block`, `diagram_compare`, `diagram_series` |
| Aside | `key_fact`, `callout`, `pitfall`, `pitfalls` |
| Worked example | `worked_example`, `worked_examples` |
| Questions | `practice`, `short_answer`, `fill_in_blank`, `student_textbox`, `reflection` |
| Choices | `quiz` |
| Answer key | derived at document level |

**Cut entirely:** `interview`, `simulation`, `video_embed` — none has an honest paper form. `simulation` currently prints as "Available in digital version," consuming space and teaching nothing.

---

## 5. Page design constraints — these drive everything

**Measure.** Single column, 65–75 characters. On A4 this means the text column cannot be full width.

**The scholar's margin.** Asymmetric two-track page:

```
┌─────────────────────────────────────┐
│   main column        │  margin      │
│   ~112mm             │  ~56mm       │
│   ~68 chars          │              │
│   prose, tables,     │  asides,     │
│   questions          │  captions    │
│   figures may span both ────────────│
└─────────────────────────────────────┘
```

Solves four problems at once: correct measure; short content stops eating full-width rows; asides get a home outside the main flow; figures can still go full-bleed.

**Baseline rhythm.** Every vertical measurement a multiple of one line height. Currently spacing is arbitrary rem values, which is the main reason pages read as "assembled" rather than "designed."

**This will be photocopied in black and white.** Teachers do this. **Never encode meaning in colour alone.** Emphasis must come from rules, indentation, weight, space and small caps — colour is a bonus, never the carrier. This single constraint invalidates most of what the current library does for emphasis.

**Ink economy.** Rules over fills. Large tints cost toner and grey out text.

**One accent colour.** The current library uses blue, amber, emerald, violet, rose, fuchsia and teal across different blocks. On paper that is noise; photocopied it is nothing.

**No box outside Aside.** Aside is the only object permitted a border. If another object seems to need one, the taxonomy is wrong.

**No labels.** No object names itself on the page.

**Type scale: four sizes total.** Body, heading, sub-heading, caption. For Grade 7 and reading-support learners, default to a humanist sans for body rather than a serif — more forgiving on cheap photocopies.

**Presets should vary typography, not palette.** Current presets vary colour and "surface style" (`blue-classroom`, `warm-paper`, `calm-green`). Page presets should vary measure, leading, size and face — `generous` / `standard` / `compact`.

---

## 6. Chromium test results — already run, treat as settled

A print-fragmentation test was rendered through headless Chromium 141 via Playwright (the same engine used for PDF export). Results:

| Test | Result |
|---|---|
| Margin column via **float** | **PASS.** Asides sit in the margin, survive page breaks, appear once, never clipped, never overlap. **Use this.** |
| Margin column via **CSS grid** | Works but worse — each aside claims a grid row, coupling row heights and creating dead space. **Reject.** |
| Table header repeat (`display: table-header-group`) | **PASS.** Header reappears on continuation pages. |
| Figure atomicity (`break-inside: avoid`) | **PASS.** Plate and caption move as one unit. |
| `orphans` / `widows` | **PASS.** No stranded lines across 7 pages. |
| Hanging indent for question numbers | **PASS.** |

### The working recipe

```css
.page   { padding-right: 62mm; }
.aside  { float: right; clear: right;
          width: 56mm; margin-right: -62mm; }
```

Container reserves the gutter; the aside floats out into it with a negative margin. `clear: right` prevents collisions when two asides land close together.

### Two confirmed gotchas — carry these into the design

1. **`hyphens: auto` silently does nothing without a `lang` attribute.** No error, no hyphens. The root element Lectio renders into must carry `lang`.

2. **`break-after: avoid` only protects the immediately following element — it does not chain.** In testing, a heading plus one following line stayed together at the bottom of a page while the figure after them jumped to the next page, stranding the heading. **Therefore Heading cannot be a standalone object: heading + first following block must be wrapped in a single `break-inside: avoid` container.** This is a real constraint on the object model.

An attached HTML file contains the working reference implementation of this geometry.

---

## 7. The biggest risk — address it head-on

**The planner may get worse before it gets better.**

Today the planner sees 33 component slugs, each with a `role` and a `cognitive_job`, plus per-lesson budgets and per-section limits. That vocabulary is doing real pedagogical work inside the prompt.

Collapse to ten objects and the palette becomes blunt. If intent does not absorb everything the component names were carrying, generated plans get blander and every section starts to look the same.

**So the intent catalogue must be richer than the object catalogue, not thinner.** Intent is where `role`, `cognitive_job` and generation hints go to live. Ten objects and eight intents will be a downgrade. Ten objects and roughly thirty intents is the target ratio.

This is the single most important design task in the project, and it must be validated before any renderer is built.

---

## 8. What to produce

Draft these as separate, complete artifacts.

**A. Fork plan.** The new library is a fresh repo, not a clone-and-delete — carrying the old structure across invites the old design to reassert itself. Specify exactly what scaffolding to carry (build config, tsconfig, vitest, the contract-export script skeleton, sanitize/markdown utilities) and what to leave behind (all components, registry, metadata, schema types, document conversion, template configs, print stylesheet, colour presets). Address: how the consuming app depends on the new library during development without publishing to npm; how both libraries can be installed simultaneously so old documents render through the old path and new ones through the new (`document_version: 2`, no migration).

**B. The contract — object catalogue and intent vocabulary.** The centrepiece. For each of the ten objects: what it holds, its content schema, its page behaviour, its fragmentation rules. For each intent: name, teacher-facing label, pedagogical role, cognitive job, which objects it is valid on, generation guidance. Aim for ~30 intents. This is the file both the library and the backend read. Specify the exported JSON shape.

**C. Validation test for the contract.** A hand-assembled planner prompt built from the new vocabulary, in the same shape the current `_planner_index_block()` produces, so it can be run against a real topic and compared against current output before anything is built. Include what "good" looks like and what failure looks like.

**D. The ten page object specs.** For each: content model, page placement (main / margin / spanning), emphasis mechanism (explicitly — this is where good-looking is won or lost), break behaviour, and the screen-decoration layer that wraps it. Build on the proven float geometry. Remember Heading binds to what follows it.

**E. Base print stylesheet.** Positive rules only — page geometry, type scale, baseline rhythm, measure, orphans/widows, hyphens with lang, figure/caption binding, table header repeat, heading binding. Target 40–60 lines. No `!important`, no override rules. Page geometry belongs in the library, not the app.

**F. Backend rewiring map.** For each touchpoint, what changes and what does not: the planner palette builder; the blueprint model; the section-writer prompt builder and schema-shape resolver; the `component_ready` → `block_ready` event; the merge function (append at `position` rather than assign to `section_field`); template configs re-expressed as intents; QC/coherence routing. Be explicit that model slots, timeouts, retries, tracing, streaming, chunked state, resume logic, admission control, the image pipeline and PDF export machinery are all untouched.

**G. Phasing plan.** Sequenced so the riskiest question is answered first and cheapest. Each phase independently verifiable with binary done-criteria and a single commit. Include a progress meter: the print stylesheet's line count should shrink monotonically — if it grows, something was built screen-first again.

---

## 9. Constraints on your output

- Be decisive. The founder prefers a clear recommendation over an options menu. Where you must choose, choose and state why.
- Assume an implementation agent (Codex) will execute from these artifacts without access to this conversation. They must be self-contained.
- Do not propose infrastructure beyond concierge scale — no job queues, no workers, no multi-provider anything.
- Do not propose keeping the old component system alongside as a compatibility layer. This is a deliberate overhaul; components were tried for a long time and did not work.
- Do not propose migrating saved documents. Version the document and let old ones age out.
- ASCII diagrams are welcome. Prose over bullet-soup where an idea needs explaining.
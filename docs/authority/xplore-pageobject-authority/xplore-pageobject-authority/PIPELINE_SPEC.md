# Native Page-Object Pipeline Specification

## 1. Entry condition

The v2 path begins only after:

- unit path is approved;
- lesson is not skipped;
- objective ownership/hash checks are green;
- unresolved prerequisite assumptions are handled;
- requested group/variant scope is valid;
- feature flag permits v2 creation for the selected scope.

## 2. Preparation sequence

### Step A — Resolve fixed context

Reuse current `planning.bridge` context construction:

- scope contract;
- prior established knowledge;
- explicit prerequisite lesson links;
- lesson actuals;
- knowledge type;
- lesson mode;
- approved skeleton/deviations;
- selected group context.

### Step B — Structural planning without components

Create a v2 structural prompt variant. It produces:

- anchor;
- one canonical concept card;
- section metadata matching skeleton slots;
- transition notes;
- misconception decisions;
- objective concern/deviation request.

It must not produce component slugs or block objects.

### Step C — Resolve candidate matrix per section

Deterministic resolver:

```text
resource allowed intents
∩ skeleton section candidate intents
∩ selectable catalogue intents
= section intents
```

For every section intent:

```text
intent valid_objects
∩ resource allowed objects
∩ first-slice implemented objects
∩ placement constraints
= explicit object candidates
```

Empty intersection is a configuration error before the LLM call.

### Step D — Plan each section

Run sections in order for the first implementation. The planner sees summaries of already planned sections so it can avoid repetition and maintain progression. Do not parallelize until plan consistency tests exist.

On `slot_concern`, stop v2 generation as `awaiting_review` or `blocked`, preserving the concern. Do not fall back silently to legacy component selection.

### Step E — Validate whole lesson block plan

Validate:

- section min/max block bounds;
- contiguous positions;
- candidate closure;
- compatibility;
- no generated headings;
- no question block without source IDs;
- practice/check expectations from skeleton;
- no block re-teaches exact `prior_established` entries based on brief/evidence checks;
- one lesson concept ownership.

Do not add global pedagogical density caps.

## 3. Content writing sequence

For each section in order, write blocks in order. Section writer concurrency may be introduced after the sequential fixture is stable.

### Prose

Use when continuous explanation or connection is the correct physical form. Respect catalogue paragraph/word capacity. Do not insert headings into paragraphs.

### List

Use when ordering, steps, glossary, or discrete parallel items are the content structure. Every item must be syntactically parallel where appropriate.

### Table

Use only when rows and columns encode a real comparison/classification/timeline relationship. The writer must declare columns first and produce complete cells. For writing resources later, blank cells need explicit contract support; do not fake them with empty strings in the lesson slice.

### Worked example

Requires a specific problem, visible steps, an answer, and optional check. `demonstrate` and `practise-guided` remain different intents even when they share the object.

### Figure

The writer produces a content brief and pending asset payload. Media execution is separate. Alt text and caption exist before the asset completes.

### Questions

Assembler only. It takes canonical item records generated behind the wall and maps them to the question object. It never receives prose paragraphs or object-writer outputs.

## 4. Assembly

Build sections from `section.title` plus completed block records. Sort only once by planned position, then rewrite positions to indexes during normalization. Any later order mismatch is an error.

The document builder does not generate educational prose.

## 5. Validation and repair

### Deterministic repair allowed

- normalize whitespace;
- normalize position/index after stable sort;
- remove unknown extra fields if generated adapter explicitly permits equivalent normalization;
- map a missing optional null to canonical null/default;
- clip only non-semantic advisory metadata where the existing product already does so.

### Deterministic repair forbidden

- truncate educational content mid-sentence;
- drop a block to meet page count;
- switch object or intent;
- invent missing question IDs;
- manufacture a misconception;
- move a figure to make layout convenient;
- rewrite scope content.

Invalid writer output should retry that writer with validation feedback, not corrupt valid content.

## 6. Persistence

The final document owner resolved in Phase 0 must store the normalized v2 JSON. Also persist enough per-block execution status to resume failed generations without re-planning successful blocks.

Minimum resumability:

- completed block content is not regenerated;
- failed block can retry independently;
- pending visual can resume independently;
- reloaded document uses committed order;
- contract/catalogue version are preserved.

## 7. API

The generation document response must be discriminated:

```json
{
  "document_version": 2,
  "document": {"...": "LectioDocumentV2"},
  "generation_status": "complete",
  "contract_version": "..."
}
```

Do not make the frontend guess v2 by looking for `sections[].blocks`.

## 8. Frontend rendering

```ts
if (payload.document_version === 2) {
  render LectioDocumentView(payload.document)
} else {
  render legacy Lectio document
}
```

The frontend may validate and display issues, but it may not reorder or reinterpret blocks.

## 9. PDF

Reuse the application’s established Playwright export path. The print route must:

- load the persisted document by generation/lesson ID;
- choose teacher/student audience in Xplore;
- render with `@lectio/page`;
- expose the existing or equivalent readiness signal;
- wait for fonts/assets or explicit pending-media policy;
- use A4 and package print CSS;
- return a stable PDF or a clear preflight failure.

## 10. Failure modes

| Failure | Required behavior |
|---|---|
| empty candidate intersection | config failure before LLM; include resource, slot, intent/object sets |
| planner chooses closed candidate | reject output and retry once with exact violation |
| repeated planner validation failure | persist blocked state; no legacy silent fallback |
| writer returns wrong object shape | retry writer only |
| question ID missing | block assembly fails; do not invent item |
| figure generation fails | preserve figure block with failed status and diagnostic |
| contract drift | CI fails before deploy |
| frontend package validation fails | show diagnostic in review route; block PDF |
| print overflow | capture page/element evidence; do not drop content automatically |

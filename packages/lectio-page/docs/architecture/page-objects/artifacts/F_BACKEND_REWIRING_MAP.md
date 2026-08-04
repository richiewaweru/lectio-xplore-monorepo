# F. Backend Rewiring Map

## Executive summary

The textbook generator's planning, orchestration, streaming, retry, tracing, persistence, visual generation, and PDF machinery remain.

The resource vocabulary changes from:

```text
component_id + section_field + data
```

to:

```text
object + intent + position + content
```

The most important code change is the merge destination. The current event already carries `position`; the wide record discards it. V2 appends and sorts ordered blocks.

## 1. Contracts directory

### Current

Backend reads legacy Lectio contracts through `LECTIO_CONTRACTS_DIR`.

### V2

Add:

```text
LECTIO_CONTRACTS_DIR_V2
```

It contains:

- `lectio-document-v2.schema.json`
- `object-catalogue.v1.json`
- `intent-catalogue.v1.json`
- `compatibility.v1.json`
- `manifest.json`

What does not change:

- configuration loading pattern;
- contract hash verification;
- startup health check concept;
- deployment model.

## 2. Planner palette builder

### Current touchpoint

`backend/src/generation/v3_studio/prompts.py`
`_planner_index_block()`

The current palette exposes component IDs, section fields, roles, cognitive jobs, budgets and limits.

### Change

Replace the v2 palette builder with:

```python
def _document_palette_block(
    object_catalogue: ObjectCatalogue,
    intent_catalogue: IntentCatalogue,
) -> str:
    ...
```

Output groups by pedagogical purpose, not renderer.

Each intent entry includes:

- intent ID;
- teacher label;
- pedagogical role;
- cognitive job;
- valid objects;
- generation guidance;
- constraints.

Object entries include:

- physical role;
- placement;
- fragmentation;
- content-schema summary.

### Does not change

- planner model;
- planner invocation;
- timeout;
- retry;
- tracing;
- prompt loading;
- SSE behavior;
- teacher brief;
- source context;
- lesson budgets as a planning concept.

## 3. Blueprint model

### Current

Blueprint sections carry component choices resembling:

```json
{
  "component_id": "explanation-card",
  "intent": "Explain"
}
```

### V2

```json
{
  "move_id": "move-3",
  "position": 2,
  "intent": "explain-cause",
  "object": "prose",
  "brief": "Explain why...",
  "must_establish": ["..."],
  "constraints": ["..."]
}
```

Pydantic model:

```python
class PlannedDocumentMove(StrictModel):
    move_id: str
    position: int = Field(ge=0)
    intent: IntentId
    object: PageObject
    brief: str
    must_establish: list[str] = Field(default_factory=list)
    must_not_introduce: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    uses_anchor_id: str | None = None
```

### Does not change

- section IDs;
- lesson IDs;
- objective ownership;
- source anchors;
- knowledge types;
- learner profiles;
- planning revision;
- teacher deviations;
- skeleton selection.

## 4. Skeleton and template configs

### Current

Templates/skeletons ultimately name component slots.

### V2

Express pedagogical moves and allowed document objects:

```yaml
- move: establish-core-model
  required_intents: [define, explain]
  allowed_objects: [prose, table, figure]
  cardinality: {min: 1, max: 3}
```

The planner chooses the exact sequence.

### Does not change

- skeleton selection by knowledge type;
- lesson modes;
- approved insert/remove/replace/reorder deviations;
- support/core/extension expansion.

## 5. Section-writer work order

### Current touchpoint

`backend/src/v3_execution/prompts/section_writer.py`

The current prompt already receives content intent separately from component contract.

### Change

Replace component cards with object contracts and intent records.

```python
class WriterDocumentObject(StrictModel):
    object_id: str
    position: int
    object: PageObject
    intent: IntentId
    brief: str
    constraints: list[str]
    uses_anchor_id: str | None = None
```

```python
class SectionWriterWorkOrder(StrictModel):
    work_order_id: str
    section: WriterSection
    objects: list[WriterDocumentObject]
    object_contracts: dict[str, Any]
    intent_contracts: dict[str, Any]
    ...
```

The writer prompt says:

1. fulfill the pedagogical intent;
2. obey the selected object's content schema;
3. do not emit styling or labels;
4. preserve source anchors;
5. output one block payload per work item.

### Schema-shape resolver

Replace component-schema lookup by object-schema lookup:

```python
schema_for_object("worked-example")
```

The content schema is keyed by `object`, never `intent`.

### Does not change

- section writer model slot;
- one-work-order execution pattern;
- source-of-truth entries;
- register;
- learner profile;
- corrections;
- consistency rules;
- timeout and retry.

## 6. Generated block models

### Remove from v2 path

```python
GeneratedComponentBlock
component_id
section_field
component_cards
```

### Add

```python
class GeneratedDocumentBlock(StrictModel):
    id: str
    section_id: str
    position: int = Field(ge=0)
    object: PageObject
    intent: IntentId
    content: dict[str, Any]
    source_work_order_id: str
```

Prefer a discriminated union for final validation.

## 7. Streaming event

### Current

```text
component_ready
```

Payload includes component ID, section field, position and data.

### V2

```text
block_ready
```

```json
{
  "generation_id": "...",
  "section_id": "...",
  "block": {
    "id": "...",
    "position": 3,
    "object": "figure",
    "intent": "trace-flow",
    "content": {}
  }
}
```

### Does not change

- SSE transport;
- event persistence;
- chunked state;
- resume cursor;
- progress reporting;
- tracing IDs;
- admission control.

## 8. Merge function

### Current critical failure

Conceptually:

```python
section[section_field] = data
```

This discards `position` and makes repeats impossible.

### V2

```python
def merge_block_ready(document: dict, event: BlockReadyEvent) -> None:
    section = find_section(document, event.section_id)
    blocks = section.setdefault("blocks", [])

    existing_index = next(
        (i for i, item in enumerate(blocks) if item["id"] == event.block.id),
        None,
    )

    payload = event.block.model_dump(mode="json")

    if existing_index is None:
        blocks.append(payload)
    else:
        blocks[existing_index] = payload

    blocks.sort(key=lambda item: (item["position"], item["id"]))
```

Requirements:

- idempotent on replay;
- stable on resume;
- no overwrite based on object type;
- duplicate object types valid;
- position collision produces deterministic order plus diagnostic;
- final normalization rewrites positions to contiguous values if teacher-approved ordering requires it.

## 9. Visual generation

Operational separation remains.

### Plan

A figure block may begin unresolved:

```json
{
  "object": "figure",
  "content": {
    "asset": {
      "status": "pending",
      "request_id": "visual-7"
    }
  }
}
```

The visual lane resolves the asset by block ID.

### Does not change

- image provider;
- SVG generation;
- visual QC;
- retries;
- fallback behavior;
- telemetry;
- visual status lifecycle.

### Important change

Final canonical figures remain in the ordered `blocks` array. Do not keep permanent detached `visual_blocks` that must be reattached during rendering.

## 10. Questions and answer keys

Question writer may remain separate.

It emits `questions` or `choices` blocks with stable question IDs.

Answer-key worker emits the document-level `answer-key` block referencing those IDs.

Does not change:

- answer-key styles;
- expected working;
- marks;
- question difficulty;
- teacher-edition selection.

## 11. QC and coherence

Replace component-specific checks with:

### Contract QC

- object schema valid;
- intent valid;
- object-intent compatible;
- IDs unique;
- positions valid;
- required asset metadata present.

### Instructional QC

- planned moves fulfilled;
- must-establish coverage;
- misconception addressed;
- source anchors respected;
- learner-group adaptation present.

### Document QC

- heading hierarchy;
- excessive asides;
- empty objects;
- repeated content;
- figure placement;
- answer-key coverage.

### Render QC

- overflow;
- blank pages;
- orphan headings;
- page-number collision;
- table truncation;
- missing math render;
- insufficient answer space.

### Does not change

- reviewer model;
- coherence pass;
- deterministic checks framework;
- review event stream;
- correction workflow.

## 12. Persistence and API

New document JSON:

```json
{
  "document_version": 2,
  "contract_version": "1.0.0",
  "sections": [
    {
      "id": "s1",
      "title": "Why the colour spreads",
      "blocks": []
    }
  ]
}
```

No database migration of v1 JSON.

The existing JSON document column can store v2 if versioned. Add a constraint or application check that v2 generation routes cannot write v1 shapes.

## 13. Frontend

Remove v2 use of:

- `SectionContent`;
- pack-to-legacy mapper;
- synthetic header insertion;
- synthetic answer-key section;
- field-name iteration.

Consume:

```ts
import type { LectioDocument } from '@lectio/page';
```

Review and print use the same document, with review chrome outside the print subtree.

## 14. Explicitly untouched systems

The implementation agent must not alter:

- model assignments;
- model providers;
- timeouts;
- retries;
- tracing;
- SSE transport;
- chunked state;
- resume logic;
- admission control;
- database job model;
- image-generation provider;
- SVG/image pipeline;
- PDF export engine;
- Playwright deployment;
- authentication;
- teacher planning UX unrelated to v2 resource preview.

**DOCUMENT VERSION:** 1.0  
**DEPENDS ON:** A, B, C, D

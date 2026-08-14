# Planning and Runtime Contracts

## 1. Planned block

Reference Python shape:

```python
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

PageObjectId = Literal[
    "prose",
    "list",
    "table",
    "figure",
    "worked-example",
    "questions",
    "aside",
    "choices",
    "heading",
    "answer-key",
]

Placement = Literal["main", "margin", "spanning"]


class PlannedBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    position: int = Field(ge=0)
    intent: str = Field(min_length=1)
    object: PageObjectId
    evidence: str = Field(min_length=1)
    brief: str = Field(min_length=1)
    role: str | None = None
    placement: Placement = "main"
    source_question_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def page_rules(self) -> "PlannedBlock":
        if self.object == "heading":
            raise ValueError("Generated first-slice plans do not emit heading blocks")
        if self.object == "questions" and not 1 <= len(self.source_question_ids) <= 6:
            raise ValueError("Questions blocks require 1..6 source_question_ids")
        if self.object == "choices" and len(self.source_question_ids) != 1:
            raise ValueError("Choices blocks require exactly one source_question_id")
        if self.object not in {"questions", "choices"} and self.source_question_ids:
            raise ValueError("Only assessment blocks carry source_question_ids")
        return self
```

Do not copy this blindly if generated catalogue literal types already exist. Use canonical generated types where possible.

## 2. Section block planner output

```python
class SectionBlockPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blocks: list[PlannedBlock]
    slot_concern: str | None = None

    @model_validator(mode="after")
    def exclusive_result(self) -> "SectionBlockPlan":
        if self.slot_concern and self.blocks:
            raise ValueError("slot_concern requires blocks=[]")
        if not self.slot_concern and not self.blocks:
            raise ValueError("A successful plan requires at least one block")
        for index, block in enumerate(self.blocks):
            if block.position != index:
                raise ValueError("Block position must equal array index")
        return self
```

The server then validates min/max section bounds and candidate closure.

## 3. Candidate matrix

The planner should not receive independent lists that permit illegal cross-products. Resolve explicit candidates:

```json
{
  "intent": "explain-cause",
  "intent_record": {
    "choose_when": "...",
    "not_when": {"trace-flow": "..."},
    "cognitive_job": "..."
  },
  "objects": [
    {
      "id": "prose",
      "earns_its_place_when": "...",
      "reject_when": "...",
      "capacity": {"paragraphsMax": 4},
      "allowed_placements": ["main"]
    },
    {
      "id": "figure",
      "earns_its_place_when": "...",
      "reject_when": "...",
      "capacity": {},
      "allowed_placements": ["main", "spanning"]
    }
  ]
}
```

Every emitted pair must exactly match one candidate entry.

Assessment candidates are ownership-driven, using the approved item record's
canonical `options` metadata as the discriminator:

- no `source_question_ids` means neither `questions` nor `choices` is legal;
- 1..6 open-response records (empty `options`) mean only `questions` is legal;
- exactly one multiple-choice record (non-empty `options`) means only `choices`
  is legal;
- mixed sources, more than six open responses, or multiple MCQs must repair the
  teaching plan before form planning;
- a block carrying `source_question_ids` never receives a non-assessment
  candidate, and adapters must never mask or discard those IDs.

## 4. Resource prompt context

This is assembled at runtime and is not persisted as a stance model:

```python
class ResourcePromptContext(BaseModel):
    resource_id: str
    resource_label: str
    resource_purpose: str
    lesson_mode: str
    prior_established: list[str]
    must_establish: list[str]
    must_not_introduce: list[str]
    terminology: list[str]
    text_policy: dict[str, object]
    validation_rules: list[str]
```

## 5. Writer context

```python
class BlockWritingContext(BaseModel):
    subject: str
    grade_level: str
    objective: str
    concept_card: dict
    prior_established: list[str]
    scope_contract: dict
    anchor: dict
    section_id: str
    section_title: str
    section_purpose: str
    planned_block: PlannedBlock
    preceding_block_summaries: list[str]
    following_block_briefs: list[str]
    object_contract: dict
    intent_guidance: dict
```

Writers receive only their assigned object contract, not alternative objects.

## 6. Content outputs

Use generated canonical document models. The first-slice writer outputs correspond to:

- `ProseContent.paragraphs`
- `ListContent.style`, `lead_in`, `items`
- `TableContent.columns`, `rows`, `caption`, `presentation`
- `WorkedExampleContent.problem`, `steps`, `answer`, `check`
- `FigureContent.asset`, `caption`, `alt_text`, `width`
- `QuestionsContent.instructions`, `items`

For assessment objects, no LLM writer output is accepted. The assembler converts
the exact referenced approved item records to `QuestionsContent` or
`ChoicesContent`. MCQ options and the correct answer remain owned by the approved
record. A `choices` answer-key entry uses the block ID as `question_id`.

## 7. Stable IDs

Recommended deterministic IDs:

```text
section id:          existing skeleton slot id or materialized variant id
block id:            <section-id>-b<1-based-position>-<object>
question item id:    canonical item-generation question_id
visual request id:   independent request UUID referenced inside figure asset
```

A completed visual changes `content.asset`, not `block.id`, `position`, `object`, or `intent`.

## 8. Versioning

Persist both:

```json
{
  "document_version": 2,
  "contract_version": "<package contract version>",
  "catalogue_version": "1.1.0"
}
```

If `catalogue_version` is not part of the public document contract, place it in metadata. Never infer it from deployment state when reading an existing document.

## 9. Backend semantic mirror

The backend must check at least:

- unique document, section, block, and question IDs;
- block position equals index;
- no generated section-title heading block duplication;
- intent/object compatibility;
- placement compatibility;
- object capacity;
- questions reference known item IDs;
- answer-key references known question IDs;
- pending figures have request IDs;
- ready figures have safe sources;
- first-slice object allowlist.

The frontend/package validator remains the final canonical semantic implementation. Mirror tests must use shared fixtures to detect drift.

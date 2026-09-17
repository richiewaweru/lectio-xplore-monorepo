# Proposed Data Contracts

Names are suggestions. Preserve repository naming conventions if implementation uses equivalent types.

## A. FlowChoice

```python
class FlowChoice(BaseModel):
    recommended_slots: list[str]
    selected_slots: list[str]
    rationale: str
    departures: list[FlowDeparture]

class FlowDeparture(BaseModel):
    operation: Literal["insert", "remove", "replace", "reorder"]
    from_slot: str | None
    to_slot: str | None
    reason: str
```

Code validates `selected_slots` against a legal slot vocabulary and hard constraints.

## B. TeachingPlanBlock additions

```python
TaskMode = Literal["none", "formative", "assessment"]

class TeachingPlanBlock(...):
    ...
    task_mode: TaskMode = "none"
    sourcebook_refs: list[str] = []
```

If sourcebook refs are created after the Teaching Plan, store them in a separate binding artifact rather than mutating an approved revision. Preferred safe pattern:

```python
class TeachingContentBinding(BaseModel):
    teaching_block_id: str
    sourcebook_refs: list[str]
    shared_task_id: str | None
```

This keeps approved Teaching Plan immutable.

## C. LessonSourcebook

```python
SourcebookEntryType = Literal[
    "definition",
    "quantitative_example",
    "worked_example_data",
    "scenario",
    "comparison_case",
    "fact_set",
    "sequence",
    "misconception_resolution",
    "stimulus",
]

class SourcebookEntry(BaseModel):
    id: str
    type: SourcebookEntryType
    purpose: str
    content: dict[str, Any]
    provenance_refs: list[str]

class LessonSourcebook(BaseModel):
    teaching_plan_id: str
    teaching_plan_revision: int
    entries: list[SourcebookEntry]
```

### Rule

Sourcebook is not learner-facing prose. It is canonical shared content state.

## D. SharedTaskSpec

```python
class SharedTaskSpec(BaseModel):
    id: str
    teaching_block_id: str
    mode: Literal["formative", "assessment"]
    action: LearnerActionId
    purpose: str
    prompt: str
    difficulty: Literal["guided", "independent"]
    sourcebook_refs: list[str]
    expected_evidence: str
    response: dict[str, Any]
    evaluation: dict[str, Any]
    feedback: dict[str, Any] | None = None
    approved_source_ids: list[str] = []
```

`response` is semantic, not UI-native. Examples:

```json
{"type":"single_choice","options":[{"id":"a","text":"..."}]}
{"type":"number"}
{"type":"text","max_length":240}
{"type":"ordered_items","items":[...]}
```

`evaluation` examples:

```json
{"type":"choice_keys","correct":["b"]}
{"type":"exact_number","value":4,"tolerance":0}
{"type":"rubric","criteria":[...]}
```

Learn maps this to retained interaction schemas.
Print maps it to paper task treatments.

## E. CoherenceReport

```python
class ReviewIssue(BaseModel):
    code: str
    severity: Literal["blocking", "warning"]
    message: str
    teaching_block_ids: list[str] = []
    node_ids: list[str] = []
    task_ids: list[str] = []
    sourcebook_refs: list[str] = []
    repair_instruction: str

class CoherenceReport(BaseModel):
    path: Literal["print", "learn"]
    status: Literal["pass", "repair_required"]
    issues: list[ReviewIssue]
```

## F. RepairTarget

```python
class RepairTarget(BaseModel):
    target_kind: Literal["document_node", "shared_task", "figure_asset"]
    target_id: str
    issue_codes: list[str]
    instruction: str
    immutable_refs: list[str]
```

Never target an entire lesson unless the structural plan itself is invalid; that should route back to planning rather than masquerade as a content repair.

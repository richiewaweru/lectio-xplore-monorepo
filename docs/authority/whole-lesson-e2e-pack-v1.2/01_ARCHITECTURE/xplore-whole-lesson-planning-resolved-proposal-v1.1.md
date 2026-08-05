# Xplore Whole-Lesson Planning Architecture
## Resolved Proposal v1.1 — Implementation Closure and Four-Run Proof

**Status:** Approved for implementation  
**Document version:** 1.1  
**Last updated:** August 5, 2026  
**Repository:** `richiewaweru/lectio-xplore-monorepo`  
**Inspected branch:** `pageobject-integration`  
**Inspected commit:** `f5ad8c6997ef78d51530928dd152be8f42b30c4b`  
**Initial mode:** `conceptual` + `first_exposure`  
**Proof target:** Four complete, recorded lesson generations through Xplore

---

## 1. Executive Summary

Xplore will replace per-slot and per-block planning with two authoritative lesson-wide planning artifacts:

1. **Whole-Lesson Teaching Plan** — one standard-tier LLM call decides the teaching arc, anchor use, section purposes, ordered teaching intents, concrete briefs, evidence references, and short decision rationales. It sees no page-object names.
2. **Whole-Lesson Form Plan** — one fast-tier LLM call assigns a compatible page object to every approved teaching block while seeing the visual rhythm of the full lesson.

The architecture remains intentionally separated:

```text
UNIT/PATH OWNS            objective, scope, anchor, concept cards, item pool
TEACHING PLANNER OWNS     teaching sequence and briefs
FORM PLANNER OWNS         page-object selection
WRITERS OWN               content inside fixed page-object contracts
CODE OWNS                 legality, persistence, events, approval, assembly, print
```

This version closes the implementation gaps around those two calls. In particular, it defines:

- how approved item records reach the planner and questions assembler;
- how both planning artifacts are durably persisted;
- dedicated timeout and retry budgets;
- three catalogue projections generated from one source;
- the mandatory teacher approval gate;
- native block-level progress events and frontend state;
- native v2 block patching;
- strict behavior when figures are pending during print;
- concrete advisory QC checks;
- model-tier routing;
- the exact execution order for the first four recorded runs.

The four runs must not omit questions. `PackItemModel` and its concept-card relationship already exist, so the correct response is to implement a typed approved-item query during lesson preparation. Removing the questions block would prove only a partial path and would weaken the end-to-end claim.

The first release may remain read-only in the full drag-and-drop Builder, but it may not be silent, unreviewable, or uneditable at the API level. A teacher must be able to inspect and approve the teaching plan before writing begins, observe native block progress, and patch an individual generated block by stable block ID.

---

## 2. Resolved Product Flow

```text
CREATE UNIT
    ↓
GENERATE PATH
    ↓
TEACHER APPROVES PATH
    ↓
PREPARE LESSON
    scope + prior + prerequisites + fixed anchor
    concept card + approved item records + skeleton
    ↓
PROJECT TEACHING GUIDANCE                  code only
    intent guidance; zero page-object names
    ↓
PLAN WHOLE LESSON                          STANDARD model
    ↓
VALIDATE / ONE TARGETED REPAIR             STANDARD model if needed
    ↓
PERSIST TEACHING PLAN
    ↓
TEACHER REVIEWS AND APPROVES APPROACH      mandatory halt
    ↓
PROJECT FORM GUIDANCE                      code only
    ↓
PLAN FORMS FOR WHOLE LESSON                FAST model
    ↓
VALIDATE / ONE TARGETED REPAIR             FAST model if needed
    ↓
PERSIST FORM PLAN
    ↓
WRITE BLOCKS                               parallel STANDARD/FAST writers
    ↓
ASSEMBLE QUESTIONS FROM APPROVED ITEMS     deterministic
    ↓
CREATE / RESOLVE FIGURE WORK ORDERS        asynchronous
    ↓
ASSEMBLE + VALIDATE LectioDocumentV2
    ↓
PERSIST + RELOAD
    ↓
RENDER IN XPLORE WITH @lectio/page
    ↓
TEACHER PDF + STUDENT PDF
```

### 2.1 Why the approval halt is after the teaching plan

The teaching plan contains the pedagogical decision. The form plan is constrained representation selection. The mandatory teacher halt therefore occurs after the teaching plan is valid and persisted but before the form planner and writers run.

This choice provides three benefits:

1. The teacher sees the lesson arc immediately after the slowest call.
2. The system does not spend writing calls on an unapproved pedagogical approach.
3. There is one meaningful approval gate rather than two ceremonial clicks.

The form plan is still persisted and inspectable. It is not a second mandatory approval gate in the initial release. A later product version may allow “review forms before writing” as an optional workspace preference.

---

## 3. Fixed Initial Skeleton

Do not introduce a new skeleton during the four-run experiment.

```text
ORIENT → EXPLAIN → CONFRONT → CHECK
```

`contrast` remains an intent, not a dedicated section.

Initial limits:

```text
Maximum sections:        4
Maximum blocks/section:  3
Maximum total blocks:   10
```

The limits are experimental guardrails. Their purpose is to test whether one call maintains concrete briefs through the final block.

---

## 4. Model-Tier Policy

Model names must be configuration, not embedded in planning code. The code routes by semantic tier.

| Call | Tier | Reason |
|---|---|---|
| Whole-lesson teaching plan | `STANDARD` | The complete pedagogical design is created here. This is the highest-leverage quality purchase. |
| Teaching-plan repair | `STANDARD` | A failed standard reasoning result should not be repaired by a weaker tier. |
| Whole-lesson form plan | `FAST` | Inputs are constrained to fixed briefs, compatible objects, and object guidance. |
| Form-plan repair | `FAST` | Same constrained task as form planning. |
| Prose writer | `STANDARD` | Carries continuous explanation and conceptual nuance. |
| Worked-example writer | `STANDARD` | Carries reasoning steps and instructional sequencing. |
| List writer | `FAST` | Shape and purpose are already fixed. |
| Table writer | `FAST` | Schema and dimensions are tightly constrained. |
| Figure-brief writer | `FAST` | Produces a visual work order, not the final pedagogy. |
| Questions | None | Deterministic assembly from approved item records. |
| Answer-key projection | `FAST` only if explanation text is absent | Correct option is stored; a short rationale may be generated under a separate contract. |

### 4.1 Quality escalation rule

If generated lessons feel flat:

```text
Raise writer quality first.
Raise planner tiers only after evidence shows the plan itself is weak.
```

A strong plan with weak prose can be rewritten. Beautiful prose built on a weak teaching plan cannot be repaired cheaply.

---

## 5. Deterministic Lesson Preparation

The preparation layer gathers all fixed decisions before any lesson-planning call.

### 5.1 Required inputs

- Unit, subject, grade, and destination objective
- Path lesson objective and concept identity
- Knowledge type and lesson mode
- Must-establish, may-include, and must-not-introduce scope
- Prior established knowledge and prerequisites
- Approved terminology and notation
- Existing conceptual first-exposure skeleton
- Typical intents by slot
- Fixed upstream anchor and carry-forward history
- Concept card, misconceptions, and approved item records

### 5.2 Approved item record source — blocking decision

The repository already contains:

```text
ConceptCardModel.items → PackItemModel
```

`WriterContext.item_records` currently defaults to an empty tuple and is never populated. The new preparation layer must query approved items before planning.

#### Required typed query

```python
@dataclass(frozen=True)
class ApprovedItemRecord:
    id: str
    card_id: str
    stem: str
    options: tuple[dict[str, object], ...]
    correct_key: str
    diagnoses: dict[str, object]

async def load_approved_item_records(
    *,
    session: AsyncSession,
    path_lesson: PathLessonModel,
    concept_card: ConceptCardModel,
) -> tuple[ApprovedItemRecord, ...]:
    ...
```

#### Selection rules

1. Resolve the concept card already attached to the prepared lesson/pack.
2. Query `PackItemModel` by both `card_id` and `pack_id`.
3. Exclude `stale == True`.
4. Preserve stable item IDs.
5. Do not convert generated lesson prose into items.
6. Return an immutable tuple in the lesson packet.

#### Empty-pool policy

For the four proof runs, an empty approved item pool is a blocking preparation error:

```text
ITEM_POOL_EMPTY
```

The preparation endpoint must stop before the teaching-planner call and expose which concept card lacks items. It must not:

- remove the CHECK section;
- manufacture items in the planner;
- convert the block brief into a question;
- silently run a lesson without questions.

If item generation is required, it must run through the existing canonical concept-card item lane before lesson preparation resumes.

### 5.3 Immutable lesson packet

The output should include typed IDs rather than unstructured prose references:

```json
{
  "lesson": {
    "path_lesson_id": "lesson-123",
    "subject": "Science",
    "grade_level": "Grade 4",
    "objective": "Explain why plants need light to make food.",
    "knowledge_type": "conceptual",
    "lesson_mode": "first_exposure"
  },
  "scope": {
    "must_establish": [{"id": "must-1", "statement": "..."}],
    "must_not_introduce": [{"id": "exclude-1", "statement": "..."}],
    "terminology": ["light", "food", "leaf"]
  },
  "anchor": {
    "id": "anchor-plant-window",
    "description": "Two identical plants in different light conditions."
  },
  "approved_items": [
    {
      "id": "item-plant-light-03",
      "card_id": "card-plant-light",
      "stem": "...",
      "options": [],
      "correct_key": "B",
      "diagnoses": {}
    }
  ],
  "slots": []
}
```

The planner may consume this packet. It may not change the objective, scope, anchor identity, item content, or skeleton.

---

## 6. Catalogue Projections — Structural Information Barrier

Add:

```text
apps/textbook-agent/backend/src/planning/catalogue_projections.py
```

One master catalogue produces three typed views.

```text
MASTER CATALOGUE
      ├── TeachingGuidanceProjection
      ├── FormGuidanceProjection
      └── WriterContractProjection
```

### 6.1 Teaching guidance

Contains only:

- intent ID;
- teaching role;
- `choose_when`;
- `not_when`;
- permitted/excluded status;
- exclusion reason.

It contains zero:

- page-object IDs;
- schemas;
- capacity values tied to objects;
- form names;
- writer instructions.

The barrier must be enforced by separate typed DTOs, not by deleting fields from a dictionary inside the prompt function.

### 6.2 Form guidance

Contains:

- object ID;
- compatible intents;
- `earns_its_place_when` / `choose_when`;
- `not_when`;
- capacity summary;
- placement restrictions.

It must not contain full generation prompts.

### 6.3 Writer contract

Contains only the already-selected object’s:

- generation guidance;
- exact content schema;
- capacity;
- object-specific validation;
- failure examples.

### 6.4 Projection tests

At minimum:

```text
[ ] Serialised teaching guidance contains no known object ID
[ ] Teaching DTO has no object/schema/capacity fields
[ ] Form DTO contains no writer prompt
[ ] Writer projection contains only one selected object
[ ] Catalogue version/hash is recorded with each plan
```

A test should enumerate every registered page-object ID and assert none appears in the serialised teaching projection.

---

## 7. Whole-Lesson Teaching Plan

### 7.1 Output shape

```json
{
  "arc": "...",
  "anchor_usage": {
    "orient": "...",
    "explain": "...",
    "confront": "...",
    "check": "..."
  },
  "misconception_focus_ids": ["misconception-1"],
  "sections": [
    {
      "slot_id": "orient",
      "specific_purpose": "...",
      "transition": null,
      "blocks": [
        {
          "id": "orient-b1",
          "position": 0,
          "intent": "orient",
          "brief": "...",
          "evidence_refs": ["lesson.objective", "anchor.anchor-plant-window"],
          "evidence": "The learner needs a visible difference to explain before the cause is stated.",
          "departure_reason": null,
          "source_question_ids": []
        }
      ]
    }
  ]
}
```

### 7.2 Evidence rule

Keep both:

```text
evidence_refs → authoritative, resolvable, machine validated
evidence      → short human-readable explanation of why this intent belongs here
```

`evidence` must explain the decision, not merely state that the block supports the objective.

### 7.3 Typical-intent legality

`from_typical` is computed by code:

```python
from_typical = block.intent not in slot.typical_intents
```

```text
typical              → departure_reason must be empty
permitted, atypical  → departure_reason required
excluded             → reject
```

---

## 8. Hard Validation, Advisory QC, and Repair

### 8.1 Hard teaching-plan validation

Blocking checks:

```text
[ ] Required slots appear exactly once and in skeleton order
[ ] Every section has at least one block
[ ] Positions are contiguous and IDs unique
[ ] Every intent is permitted
[ ] Excluded intents do not appear
[ ] Typical/atypical departure rules hold
[ ] Every evidence reference resolves
[ ] No object ID appears in the teaching artifact
[ ] No heading block appears
[ ] Section and lesson block limits hold
[ ] Anchor identity is unchanged
[ ] Source item IDs exist in the approved item pool
[ ] No question content appears in planner output
[ ] Every must-establish statement is referenced
[ ] Brief passes deterministic minimum-quality heuristics
```

### 8.2 Deterministic brief heuristics

Block when:

- fewer than 15 words;
- no anchor ID or approved terminology term appears;
- an excluded term appears;
- a page-object ID appears;
- a banned generic phrase appears.

Initial banned phrases:

```text
explain the concept clearly
give a useful example
provide an engaging introduction
ask students what they learned
help learners understand
create a clear explanation
```

These rules catch obvious collapse; they do not claim to measure pedagogy fully.

### 8.3 Advisory teaching-plan QC

Record but do not automatically block:

| Code | Check |
|---|---|
| `LATE_BRIEF_THINNING` | Final-quarter briefs have substantially lower word count or approved-term density than first-quarter briefs. |
| `REPEATED_TEACHING_JOB` | Same intent appears in three consecutive blocks without a rationale. |
| `GENERIC_EVIDENCE` | Evidence sentence is short or matches generic-decision phrases. |
| `ANCHOR_USAGE_GAP` | The fixed anchor is introduced but not reused where the arc says it will be. |
| `MISCONCEPTION_NOT_CONFRONTED` | A focused misconception is not referenced in CONFRONT. |
| `CHECK_WEAKLY_LINKED` | CHECK lacks objective/must-establish references or selected items lack the expected concept linkage. |
| `SECTION_IMBALANCE` | One section carries most blocks while another required section is skeletal. |
| `POSSIBLE_DUPLICATION` | Two briefs share high lexical overlap and the same intent. |

### 8.4 Form-plan hard validation

```text
[ ] Every block has exactly one form
[ ] No block is added, removed, reordered, or renamed
[ ] Intent/brief/evidence are unchanged
[ ] Object is compatible with intent and resource mode
[ ] No heading object appears
[ ] Questions blocks preserve source item IDs
[ ] Placement value is legal
```

### 8.5 Advisory form QC

| Code | Check |
|---|---|
| `FORM_STREAK` | Same object selected three consecutive times without a specific reason. |
| `FORM_DOMINANCE` | One non-question form dominates the lesson beyond the configured threshold. |
| `FIGURE_OVERUSE` | More than two figure blocks or consecutive figures. |
| `CAPACITY_RISK` | Brief cues suggest content larger than the selected form’s summary capacity. |
| `VISUAL_RHYTHM_FLAT` | Sections use the same lead form repeatedly. |

### 8.6 Repair and transport-failure budget

A planner gets at most two model attempts total.

```text
Attempt 1
   ├── valid → continue
   ├── schema/legality failure → targeted repair as Attempt 2
   └── timeout/transport failure → fresh retry as Attempt 2

Attempt 2 failure → hard stop
```

Do not allow both a transport retry and a later repair to produce a third call.

The repair receives:

- complete original plan;
- exact failures with JSON paths and error codes;
- immutable paths;
- instruction to change only invalid fields.

No fixture or legacy fallback is permitted.

---

## 9. Dedicated Timeout Budgets

The existing stage-one timeout was not designed specifically for a lesson-wide structured output. Add dedicated settings:

```python
page_lesson_plan_timeout_seconds: int = 420
page_form_plan_timeout_seconds: int = 120
page_standard_writer_timeout_seconds: int = 180
page_fast_writer_timeout_seconds: int = 90
page_planning_heartbeat_seconds: int = 5
```

Environment names should be documented in `.env.example`.

### 9.1 Timeout behavior

- Emit `planning_timeout` with stage and attempt.
- Persist the error and raw response metadata, not partial content as an approved plan.
- A first-attempt timeout may use the second and final attempt.
- A second timeout ends the generation in a structured recoverable-failure state.
- The UI offers “retry planning” explicitly; it does not silently loop.

The 420-second value is a safety ceiling, not an expected latency target. Telemetry should record actual p50/p95 before tightening it.

---

## 10. Persistence of Planning Artifacts

The teaching plan and form plan are product artifacts, not transient prompt outputs.

For the initial implementation, avoid a database migration by storing native planning state behind a repository abstraction in the existing JSON-capable generation state.

Recommended shape:

```json
{
  "page_document_v2": {
    "schema_version": 1,
    "lesson_packet": {},
    "catalogue": {
      "version": "...",
      "teaching_projection_hash": "...",
      "form_projection_hash": "..."
    },
    "teaching_plan": {},
    "teaching_validation": {},
    "teaching_review": {
      "status": "pending|approved|rejected",
      "reviewed_by": null,
      "reviewed_at": null,
      "revision": 1
    },
    "form_plan": null,
    "form_validation": null,
    "block_execution": {},
    "advisory_qc": []
  }
}
```

Store this under `GenerationModel.chunked_state_json` through a dedicated `PageDocumentRepository`. The final `LectioDocumentV2` remains in `GenerationModel.document_json`.

### 10.1 Why a repository abstraction is required

The first implementation may use JSONB. Later, plan revisions or audit history may move to dedicated tables. Callers should not know the storage choice.

Required methods:

```python
save_lesson_packet(...)
save_teaching_plan(...)
save_teaching_review(...)
save_form_plan(...)
save_block_result(...)
save_qc_report(...)
save_document(...)
load_page_generation_state(...)
```

Every write should update `last_heartbeat` and use a transaction.

---

## 11. Mandatory Teacher Review Gate

### 11.1 State transition

```text
planning_teaching
    ↓
awaiting_teaching_approval
    ├── approved → planning_forms
    └── rejected → rejected_by_teacher
```

No form planning or writer call may begin before approval.

### 11.2 API surface

Suggested endpoints:

```text
GET  /generations/{generation_id}/lesson-approach
POST /generations/{generation_id}/lesson-approach/approve
POST /generations/{generation_id}/lesson-approach/reject
```

Approval payload includes `expected_revision` to prevent approving stale data.

```json
{
  "expected_revision": 1,
  "teacher_note": "Approved"
}
```

Rejecting does not automatically call the LLM. The teacher may choose explicit regeneration with feedback through a separate command.

### 11.3 Review UI

Display one top-to-bottom artifact:

```text
Lesson arc
Fixed anchor and use across sections
Focused misconceptions
ORIENT blocks
EXPLAIN blocks
CONFRONT blocks
CHECK blocks
Atypical departures and reasons
Advisory warnings
```

The final brief should be easy to inspect without opening debug logs.

---

## 12. Native Events and Progress UX

The v2 path must not emit only `component_ready` or remain silent.

### 12.1 Event vocabulary

```text
lesson_packet_ready
teaching_plan_started
planning_heartbeat
teaching_plan_ready
teaching_plan_failed
awaiting_teaching_approval
teaching_plan_approved
form_plan_started
form_plan_ready
form_plan_failed
block_queued
block_started
block_ready
block_failed
visual_pending
visual_ready
visual_failed
qc_warning
document_assembling
document_ready
generation_failed
```

Every block event includes:

```json
{
  "generation_id": "...",
  "section_id": "explain",
  "block_id": "explain-b2",
  "position": 1,
  "object": "prose",
  "status": "ready"
}
```

### 12.2 Progress experience

Do not fabricate a percentage during the long teaching-plan call.

Before completion:

```text
Designing the lesson approach… 32s
```

Emit a heartbeat every configured interval with stage and elapsed time.

When the plan completes, publish the arc and section summaries immediately and enter the approval state. This is better pedagogical progress than showing empty sections one by one.

After approval:

```text
Choosing forms…
Writing 3 of 8 blocks…
Generating 1 visual…
Assembling lesson…
```

The frontend should maintain separate counters for planned blocks, ready blocks, failed blocks, and pending visuals.

---

## 13. Native Writers and Question Assembly

### 13.1 Writer routing

```text
prose              STANDARD
worked-example     STANDARD
list               FAST
table              FAST
figure brief        FAST
questions           deterministic
```

Each writer receives:

- immutable lesson context;
- fixed block ID, intent, brief, evidence, and form;
- neighboring briefs/summaries;
- only its selected writer contract;
- optional one-variable variant contract.

Writers may not change planning fields.

### 13.2 Questions

The planner may place a `questions` block and select IDs from the approved item pool. It may not write item content.

The executor loads the same typed `ApprovedItemRecord` values into `WriterContext.item_records`. `assemble_questions` resolves every selected ID deterministically and should include the fields required by `@lectio/page`, including answer-key references for teacher edition.

Missing selected IDs are hard failures, not placeholder questions.

---

## 14. Native Block Patch Route

The existing component ref shape does not apply to v2. Add stable block-ID addressing.

Suggested endpoint:

```text
PATCH /generations/{generation_id}/page-blocks/{block_id}
```

Request:

```json
{
  "expected_document_revision": 3,
  "content_patch": {
    "paragraphs": ["Revised teacher text..."]
  }
}
```

Rules:

1. Locate the block by globally unique block ID inside the generation.
2. Permit content changes only; do not change block ID, section, position, object, or intent.
3. Apply JSON Merge Patch semantics to `content`.
4. Validate the selected object schema.
5. Validate the complete `LectioDocumentV2`.
6. Increment `document_revision` atomically.
7. Emit `block_patched`.
8. Reject stale revisions with HTTP 409.

Planning-artifact editing may be added later. For the first release, the teacher can approve/reject the approach and patch generated content by block ID. Full Builder canvas editing remains deferred.

---

## 15. Figure Lifecycle and Print Policy

Figure block identity and request ID must remain stable across callbacks.

```text
planned figure block
    ↓
FAST figure-brief writer
    ↓
persist pending asset with deterministic request ID
    ↓
visual work order
    ↓
visual_ready / visual_failed
    ↓
update only block.content.asset
```

Derive request identity from stable execution data rather than a new UUID on every retry:

```text
hash(generation_id + block_id + figure_prompt_version)
```

### 15.1 Printing while assets are pending

Final export is strict by default.

```text
POST /generations/{id}/print?edition=teacher
```

If any required visual is `pending` or `failed`, return HTTP 409 with the affected block IDs.

Optional draft behavior:

```text
POST /generations/{id}/print?edition=teacher&allow_placeholders=true
```

This may render explicit placeholders and a draft warning. It must not count as a successful proof artifact.

All four recorded teacher and student PDFs must use strict mode with every required figure ready.

---

## 16. Variants

Plan the canonical lesson once. Apply variants during writing.

Fixed across variants:

- objective;
- skeleton and section order;
- arc;
- anchor identity;
- block IDs;
- intents;
- forms;
- source item IDs.

One variant may change one declared variable, such as reading complexity, scaffolding, vocabulary support, language, or example context.

If a change requires a different objective, sequence, misconception strategy, or intent, it is a separate lesson plan, not a variant.

Variants are not required for the first four proof runs unless the existing unit flow mandates an `everyone` variant record. The architecture must preserve the boundary, but variant quality expansion should not delay the canonical end-to-end proof.

---

## 17. Implementation Order

This is the engineering order, not the four recorded generation runs.

### 17.1 Establish honest inputs and barriers

1. Add typed approved-item loading from `PackItemModel`.
2. Fail preparation with `ITEM_POOL_EMPTY` when required records are absent.
3. Add `catalogue_projections.py` and structural no-object-leak tests.
4. Add model-tier and dedicated timeout configuration.

### 17.2 Build and persist the teaching approach

5. Add lesson packet schema.
6. Add whole-lesson teaching-plan schema and prompt.
7. Add hard validation, advisory QC, and two-attempt policy.
8. Persist packet, plan, validation report, raw call metadata, and catalogue hashes.
9. Emit native planning events.
10. Add the mandatory teacher approval state and endpoints.

### 17.3 Complete native generation

11. Add whole-lesson form planner and form validation.
12. Persist the form artifact.
13. Replace stub writers with tiered LLM writers.
14. Populate `WriterContext.item_records` from the prepared approved-item pool.
15. Add native block executor, events, and final document persistence.
16. Wire stable figure work orders into the live callback.

### 17.4 Complete the product surface

17. Update frontend stream state for native events and approval.
18. Render persisted v2 document with `@lectio/page`.
19. Add strict teacher/student print behavior.
20. Add native block patch route.
21. Capture the complete evidence package.

### 17.5 Proof and cleanup

22. Execute Run 1 and read the last brief first.
23. Correct architecture defects revealed by Run 1.
24. Execute Runs 2–4.
25. Only after all four pass, disconnect and delete unreachable legacy generation routes.

---

## 18. Four Recorded Lesson Runs

| Run | Lesson | Coverage |
|---|---|---|
| 1 | Grade 4 Science — Why Plants Need Light to Make Food | Cause, fixed anchor, misconception, table/figure/questions |
| 2 | Grade 6 Mathematics — Understanding Equivalent Fractions | Representation, explanation, worked example, item checks |
| 3 | Grade 8 Economics — How Supply and Demand Affect Price | Causal model, comparison, graph/table interpretation |
| 4 | Grade 7 English — Distinguishing a Claim from Supporting Evidence | Non-STEM proof and hard-coded-domain detection |

Every run follows:

```text
unit creation
→ path generation
→ path approval
→ lesson preparation including approved items
→ teaching plan
→ validation/repair
→ persisted teacher approval
→ form plan
→ real writers
→ deterministic questions
→ resolved figures
→ persisted LectioDocumentV2
→ database reload
→ Xplore render
→ strict teacher PDF
→ strict student PDF
```

### 18.1 Required evidence package

```text
docs/evidence/generation-runs/run-XX-<slug>/
├── 01-unit-input.json
├── 02-path-plan.json
├── 03-path-approval.json
├── 04-lesson-packet.json
├── 05-approved-item-records.json
├── 06-teaching-guidance.json
├── 07-teaching-plan.json
├── 08-teaching-validation.json
├── 09-teacher-approval.json
├── 10-form-guidance.json
├── 11-form-plan.json
├── 12-form-validation.json
├── 13-writer-results.json
├── 14-visual-work-orders.json
├── 15-advisory-qc.json
├── 16-persisted-document.json
├── 17-reloaded-document.json
├── 18-generation-page.png
├── 19-teacher.pdf
├── 20-student.pdf
├── 21-event-log.jsonl
├── 22-llm-call-summary.json
└── MANIFEST.md
```

### 18.2 Run-1 decision gate

Before Runs 2–4, inspect:

1. final brief first;
2. first brief second;
3. evidence quality across all blocks;
4. repeated teaching jobs;
5. object leakage;
6. form repetition;
7. item IDs and question integrity;
8. event completeness;
9. persistence and approval state.

If the final briefs thin out, use the approved fallback:

```text
one global arc call
    ↓
parallel section-brief expansion
    ↓
one combined validated teaching plan
```

Do not return to independent per-slot planning.

---

## 19. Deferred Until After the Four Runs

These are legitimate needs but should not block the first canonical proof:

- full drag-and-drop Builder support for v2;
- durable block-level resume after process restart;
- normalized planning-artifact database tables;
- extensive variant generation;
- block-level cost dashboards and departure-rate telemetry UI;
- legacy-path deletion.

Even when deferred, the initial code must not make them impossible. Stable block IDs, repository abstraction, explicit state, and native events are required now.

---

## 20. Legacy Boundary

Do not delete the old path before proof, but do not let it participate in new v2 generation.

The native path must bypass:

- per-slot `plan_section_blocks`;
- runtime fixture planning;
- first-candidate fallbacks;
- `ComponentSlot` creation;
- `GeneratedComponentBlock`;
- `V3SectionBuilder`;
- `SectionContent`;
- component-based progress and patch identities;
- v1 print adapters for `document_version=2`.

After all four proof runs pass, create a reachability inventory and remove the old generation routes that are no longer used. Historical v1 document reading may remain in an isolated compatibility module.

---

## 21. Testing Strategy

### 21.1 Unit and contract tests

```text
[ ] Approved items load by card/pack and stale items are excluded
[ ] Empty item pool stops preparation
[ ] Teaching projection contains zero object IDs
[ ] Whole-lesson schema accepts four ordered sections
[ ] Evidence references resolve
[ ] Typical/atypical departure rules hold
[ ] Generic briefs fail deterministic checks
[ ] Planner gets at most two model attempts
[ ] Teaching plan persists and reloads exactly
[ ] Approval rejects stale revision
[ ] No form/writer call occurs before approval
[ ] Form plan maps exactly one object to every block
[ ] Writer routing uses configured tier
[ ] Questions resolve only approved item IDs
[ ] Block events include stable IDs
[ ] Figure callback preserves block identity
[ ] Final print blocks on pending visuals
[ ] Block patch validates object and document schemas
```

### 21.2 Integration tests

```text
[ ] Unit/path data becomes one immutable lesson packet
[ ] Teaching plan transitions generation to awaiting_teaching_approval
[ ] Approval resumes form planning
[ ] Form plan and block results persist under native state
[ ] Native executor assembles LectioDocumentV2 without component pipeline
[ ] Frontend receives lesson_plan_ready and block_ready events
[ ] Generated document reloads from database
[ ] Teacher and student editions apply correct answer policy
```

### 21.3 End-to-end acceptance

For each of the four runs:

```text
[ ] No fixture planner
[ ] No missing question source
[ ] No legacy component conversion
[ ] Real LLM calls recorded at intended tiers
[ ] Teacher approval recorded
[ ] Every block emits native events
[ ] Every figure is ready before strict print
[ ] LectioDocumentV2 persists and reloads
[ ] Xplore renders the stored document
[ ] Teacher PDF succeeds
[ ] Student PDF succeeds
```

---

## 22. Tradeoffs and Risks

### Item source first vs. omit questions

**Implement item source first**

- Advantages: proves the real question wall and complete lesson path.
- Disadvantages: adds a repository query and preparation failure state before Run 1.
- Risk: concept cards may exist without items, exposing an upstream defect.
- Decision: **selected**. The defect should be surfaced, not hidden.

**Omit questions for the four runs**

- Advantages: faster arc-only experiment.
- Disadvantages: cannot claim end-to-end completeness; CHECK behavior and teacher/student answer policy remain unproven.
- Decision: **rejected for the official four runs**. An isolated planner harness may omit questions for prompt experimentation, but it is not a product proof.

### Approval after teaching plan vs. after complete document

**After teaching plan**

- Advantages: teacher controls pedagogy before expensive writing; early meaningful progress surface.
- Disadvantages: teacher does not approve the form plan separately.
- Decision: **selected**.

**After assembly only**

- Advantages: teacher sees final output.
- Disadvantages: expensive work happens before pedagogical approval.
- Decision: rejected as the only gate. Post-generation patching remains available.

### Existing JSON state vs. new tables

**Existing JSON state through repository abstraction**

- Advantages: avoids migration during proof; sufficient durability.
- Disadvantages: weaker querying and audit history.
- Decision: selected for initial proof.

**Dedicated tables now**

- Advantages: normalized revisions and analytics.
- Disadvantages: larger migration surface before product truth is established.
- Decision: defer.

---

## 23. Definition of Done

The v1.1 architecture is complete when:

```text
[ ] Approved item records are loaded into the lesson packet
[ ] Questions never use planner/writer prose
[ ] Teaching catalogue projection structurally contains no objects
[ ] One standard-tier whole-lesson teaching call replaces slot calls
[ ] Teaching plan and validation are persisted
[ ] Teacher approval is mandatory and durable
[ ] One fast-tier whole-lesson form call assigns every block
[ ] Form plan and validation are persisted
[ ] Real tiered writers replace deterministic stubs
[ ] Native block executor bypasses the component pipeline
[ ] Native block events drive the Xplore progress UI
[ ] Stable figure lifecycle reaches ready before final print
[ ] Native block patching works by block ID
[ ] LectioDocumentV2 persists and reloads
[ ] Xplore renders the stored v2 document
[ ] Strict teacher and student PDFs succeed
[ ] Four complete evidence packages exist
[ ] The final brief in each lesson remains concrete
[ ] No official run omits questions, uses fixtures, or converts through legacy components
```

---

## 24. Version and Dependencies

**DOCUMENT VERSION:** 1.1  
**LAST UPDATED:** August 5, 2026  
**DEPENDS ON:** native Lectio page-object contracts, Xplore unit/path planning, concept-card item lane, current conceptual first-exposure skeleton, `@lectio/page` rendering and print support  
**CHANGES FROM 1.0:** added model tiers; made approved-item loading a first blocker; defined timeout budgets; made plan persistence concrete; located the mandatory teacher gate; added native block events and progress UX; specified block patching; settled pending-figure print behavior; defined advisory QC checks; reordered implementation around the four proof runs; removed restart/resume as a proof blocker; retained legacy cleanup until after evidence.

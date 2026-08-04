# Textbook Generator v3 — Proposal 2: Executor Layer

## Purpose

Proposal 1 delivered the brain: Signal Extractor → Clarification →
Lesson Architect → Production Blueprint → WorkOrders.

Proposal 2 delivers the hands: the scoped executors that turn WorkOrders
into generated content, the assembler that builds the resource in blueprint
order, and the frontend canvas that fills in component by component as
each piece completes.

**Scope:** Backend execution layer · Generated block models · Section writer ·
Question writer · Visual executor · Answer key generator · v3 assembler ·
SSE runtime · Frontend canvas skeleton · SSE event handlers

**Out of scope:** Coherence reviewer · Surgical repair routing ·
Frontend brief builder collapse · Staging environment
(all covered in Proposal 3 and beyond)

**Prerequisite:** Proposal 1 complete and verified. All four persona
blueprints validate. WorkOrder compiler produces correct WorkOrders.
Lesson Architect producing valid blueprints on real briefs.

**Codebase:** Textbook Generator backend + frontend. No Lectio changes.

---

## The Rule for Every Executor

```
Executors execute. They do not plan.

They do not add unplanned components.
They do not remove planned components.
They do not change anchor facts.
They do not change question difficulty.
They do not change expected answers.
They do not create extra visuals.
They do not reorder sections.
They do not invent new numbers, units, labels, or examples.
```

The Lesson Architect is the brain. Executors are skilled workers
executing a job sheet. Rich context, zero autonomy.

---

## Backend File Structure

All new code lives in `backend/src/v3_execution/`. No v2 files modified.

```
backend/src/v3_execution/
  __init__.py

  models.py                    # GeneratedBlock output contracts

  executors/
    __init__.py
    section_writer.py          # replaces content_generator in v3 path
    question_writer.py         # new — separated from section writing
    visual_executor.py         # replaces diagram_generator in v3 path
    answer_key_generator.py    # new — explicit answer key executor

  prompts/
    section_writer.py          # prompt builders
    question_writer.py
    visual_executor.py
    answer_key.py

  assembly/
    section_builder.py         # builds SectionContent from generated blocks
    pack_builder.py            # assembles full resource from sections

  runtime/
    runner.py                  # orchestrates executor parallelism
    events.py                  # SSE event definitions and emitters
    validation.py              # executor-level validation (Level 1)
```

---

## Step 1 — Generated Block Models

**File:** `backend/src/v3_execution/models.py`

Every executor returns a typed block. Every block carries
`source_work_order_id` so any output is traceable back to its WorkOrder.
This traceability is what makes surgical repair possible in Proposal 3.

```python
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field


class GeneratedComponentBlock(BaseModel):
    block_id: str
    section_id: str
    component_id: str        # matches Lectio manifest component_id
    section_field: str       # matches Lectio sectionField
    position: int            # position within section
    data: dict[str, Any]     # validated against Lectio component schema
    source_work_order_id: str


class GeneratedQuestionBlock(BaseModel):
    question_id: str
    section_id: str
    difficulty: str          # warm | medium | cold | transfer
    data: dict[str, Any]
    expected_answer: str     # preserved from blueprint — never changed
    expected_working: Optional[str] = None
    diagram_required: bool = False
    source_work_order_id: str


class GeneratedVisualBlock(BaseModel):
    visual_id: str
    attaches_to: str              # section_id or question_id
    frame_index: Optional[int] = None   # for diagram_series frames
    mode: Literal["diagram", "diagram_series", "image", "simulation"]
    image_url: Optional[str] = None     # GCS URL — required for diagram/image
    html_content: Optional[str] = None  # required for simulation
    fallback_image_url: Optional[str] = None  # simulation print fallback
    caption: Optional[str] = None
    alt_text: Optional[str] = None
    source_work_order_id: str

    # Validation:
    # diagram / image / diagram_series → image_url required
    # simulation → html_content or fallback_image_url required


class GeneratedAnswerKeyBlock(BaseModel):
    answer_key_id: str
    style: Literal["answers_only", "brief_explanations", "full_working"]
    entries: list[dict[str, Any]]
    source_work_order_id: str


class ExecutionResult(BaseModel):
    generation_id: str
    blueprint_id: str
    component_blocks: list[GeneratedComponentBlock] = Field(
        default_factory=list
    )
    question_blocks: list[GeneratedQuestionBlock] = Field(
        default_factory=list
    )
    visual_blocks: list[GeneratedVisualBlock] = Field(
        default_factory=list
    )
    answer_key: Optional[GeneratedAnswerKeyBlock] = None
    warnings: list[str] = Field(default_factory=list)
```

**Verification:**
```
□ All block types import and instantiate without error
□ source_work_order_id present on every block type
□ GeneratedVisualBlock has frame_index for series support
□ ExecutionResult aggregates all block types correctly
```



---

## Step 1b — CompiledWorkOrders and DraftPack

These two models are referenced throughout Proposal 2 but must be
explicitly defined so the coding agent has a complete contract.

**File:** `backend/src/v3_execution/models.py` (add to same file)

```python
class CompiledWorkOrders(BaseModel):
    generation_id: str
    blueprint_id: str
    section_orders: list[SectionWriterWorkOrder]
    question_orders: list[QuestionWriterWorkOrder]  # per section
    visual_orders: list[VisualGeneratorWorkOrder]
    answer_key_order: Optional[AnswerKeyWorkOrder] = None
    review_order: Optional[CoherenceReviewWorkOrder] = None


class DraftPack(BaseModel):
    generation_id: str
    blueprint_id: str
    status: Literal["draft_ready", "partial", "failed"]
    sections: list[dict]   # SectionContent-compatible, validated against
                           # Lectio section-content-schema.json
    answer_key: Optional[GeneratedAnswerKeyBlock] = None
    warnings: list[str] = Field(default_factory=list)


class ExecutorOutcome(BaseModel):
    """Wrapper returned by every executor.
    Avoids exceptions being the only control flow for failures."""
    ok: bool
    blocks: list[Any] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    retried: bool = False
```

Every executor returns `ExecutorOutcome`, not a raw list of blocks.
The runner checks `outcome.ok` before adding blocks to `ExecutionResult`.
Failed outcomes with `retried=True` are flagged in `ExecutionResult.warnings`
for Proposal 3's coherence reviewer.

---

## Step 2 — Executor-Level Validation

**File:** `backend/src/v3_execution/runtime/validation.py`

Two levels of validation exist across v3. This step defines Level 1
which runs immediately after each executor call — before the block
is accepted into the ExecutionResult.

```
Level 1 — executor-level (this proposal)
  Runs immediately after each executor
  Deterministic schema checks only
  Failure → immediate single retry of that WorkOrder
  Still fails → flag as warning, send to coherence reviewer in Proposal 3

Level 2 — coherence review (Proposal 3)
  Runs after all executors complete
  Deterministic + LLM judgment checks
  Cross-section consistency, register match, visual alignment
  Failure → surgical repair via RepairTarget
```

Level 1 checks per executor (lightweight and deterministic only —
deep anchor drift and semantic coherence belong to Proposal 3):

```python
# Section writer checks
def validate_component_block(
    block: GeneratedComponentBlock,
    work_order: SectionWriterWorkOrder,
    manifest: dict
) -> list[str]:
    errors = []

    # component_id exists in WorkOrder
    planned_ids = [c.component_id for c in work_order.section.components]
    if block.component_id not in planned_ids:
        errors.append(f"Unplanned component: {block.component_id}")

    # section_field matches Lectio manifest
    manifest_component = manifest.get(block.component_id)
    if manifest_component:
        if block.section_field != manifest_component["sectionField"]:
            errors.append(f"section_field mismatch for {block.component_id}")

    # anchor facts — Level 1 checks obvious violations only
    # (e.g. wrong unit token in data, clearly different number)
    # Deep semantic anchor drift is detected by Proposal 3 coherence reviewer
    if work_order.section.components:
        for comp in work_order.section.components:
            if comp.uses_anchor_id:
                errors += check_anchor_units_present(
                    block.data,
                    work_order.source_of_truth,
                    comp.uses_anchor_id
                )  # lightweight check only — not full semantic validation

    return errors


# Question writer checks
def validate_question_block(
    block: GeneratedQuestionBlock,
    work_order: QuestionWriterWorkOrder
) -> list[str]:
    errors = []
    planned_ids = [q.id for q in work_order.questions]

    if block.question_id not in planned_ids:
        errors.append(f"Unplanned question: {block.question_id}")

    planned = next(
        (q for q in work_order.questions if q.id == block.question_id),
        None
    )
    if planned:
        if block.difficulty != planned.difficulty:
            errors.append(
                f"Difficulty changed: {planned.difficulty} → {block.difficulty}"
            )
        if block.expected_answer != planned.expected_answer:
            errors.append(
                f"Expected answer changed for {block.question_id}"
            )

    return errors


# Visual executor checks
def validate_visual_block(
    block: GeneratedVisualBlock,
    work_order: VisualGeneratorWorkOrder
) -> list[str]:
    errors = []

    if block.visual_id != work_order.visual.id:
        errors.append(f"visual_id mismatch")

    if not block.image_url.startswith("https://storage.googleapis.com"):
        errors.append("image_url not a valid GCS URL")

    return errors
```

**Verification:**
```
□ Validation runs after every executor call before block is accepted
□ Unplanned component_id triggers error and retry
□ Changed expected_answer triggers error and retry
□ Anchor fact violation triggers error and retry
□ Single retry attempted on failure before flagging as warning
□ Warnings collected in ExecutionResult.warnings for Proposal 3
```

---

## Step 3 — Section Writer

**File:** `backend/src/v3_execution/executors/section_writer.py`
**Prompt:** `backend/src/v3_execution/prompts/section_writer.py`

Restructures `content_generator` in the v3 path. The section writer
generates component data only for the components listed in its
`SectionWriterWorkOrder`. Nothing more.

### What it receives

The `SectionWriterWorkOrder` carries everything needed for quality
without giving the executor planning authority:

```
section.components          → exactly which components to write
section.learning_intent     → what this section is teaching
section.constraints         → specific rules for this section
section.register_notes      → any section-specific tone adjustment
register                    → prose complexity, sentence length, tone
learner_profile             → reading load, pacing, language support
support_adaptations         → concrete effects for this class
source_of_truth             → anchor facts, fixed terms, fixed units
consistency_rules           → what must not change anywhere
manifest_components         → Lectio schema for each planned component
```

### Prompt structure

```python
def build_section_writer_prompt(
    order: SectionWriterWorkOrder
) -> str:
    components_list = "\n".join(
        f"- {c.teacher_label} ({c.component_id}): {c.content_intent}"
        for c in order.section.components
    )

    return f"""You are a section writer, not a lesson planner.

Your job is to generate component content for one section of a lesson.
You have been given a precise work order. Follow it exactly.

SECTION: {order.section.title}
LEARNING INTENT: {order.section.learning_intent}

COMPONENTS TO WRITE:
{components_list}

REGISTER:
- Level: {order.register.level}
- Sentence length: {order.register.sentence_length}
- Vocabulary: {order.register.vocabulary_policy}
- Tone: {order.register.tone}
- Avoid: {', '.join(order.register.avoid)}

LEARNER PROFILE:
{order.learner_profile.level_summary}
Reading load: {order.learner_profile.reading_load}
Language support: {order.learner_profile.language_support}
Pacing: {order.learner_profile.pacing}

SUPPORT ADAPTATIONS:
{format_support_adaptations(order.support_adaptations)}

ANCHOR FACTS (do not change these):
{format_source_of_truth(order.source_of_truth)}

CONSISTENCY RULES:
{format_consistency_rules(order.consistency_rules)}

SECTION CONSTRAINTS:
{chr(10).join(f'- {c}' for c in order.section.constraints)}

STRICT RULES:
- Generate only the components listed above. Do not add others.
- Do not add diagrams, questions, or visuals. Those are separate.
- Do not change anchor facts, units, or fixed terms.
- Do not change the section order or structure.
- Write in the register specified. Do not drift to a different tone.

Return JSON matching the component schemas provided.
One key per component's section_field.
"""
```

### What it returns

```python
list[GeneratedComponentBlock]
```

One block per component in the WorkOrder. No extras.

### Validation (Level 1)

After generation, before accepting output:
```
□ component_id for every block exists in the WorkOrder
□ section_field matches Lectio manifest for that component_id
□ anchor units present in output if anchor was used
          (lightweight check — full anchor drift in Proposal 3)
□ no extra component blocks returned
```

---

## Step 4 — Question Writer

**File:** `backend/src/v3_execution/executors/question_writer.py`
**Prompt:** `backend/src/v3_execution/prompts/question_writer.py`

New executor — separated from section writing because questions have
their own strict contract that drifts when mixed with prose generation.

Question WorkOrders are compiled per section, not as one global order.
This means one failed question batch cannot block all questions across
the resource, and section-level streaming works cleanly.

The compiler produces:
```
compile_question_orders() -> list[QuestionWriterWorkOrder]
```
Each order carries the questions for one section. They run in parallel
in Wave 1 alongside section writing.

### What it receives

```
section_id          → which section these questions belong to
questions           → QuestionPlanItem list for this section only
source_of_truth     → anchor facts, fixed terms, units
register            → same register as the rest of the lesson
consistency_rules   → what must not change
```

### Prompt structure

```python
def build_question_writer_prompt(
    order: QuestionWriterWorkOrder
) -> str:
    questions_spec = "\n\n".join(
        f"""Question {q.id}:
  Difficulty: {q.difficulty}
  Skill target: {q.skill_target}
  Scaffolding: {q.scaffolding}
  Purpose: {q.purpose}
  Uses anchor: {q.uses_anchor_id or 'no'}
  Expected answer: {q.expected_answer}
  Expected working: {q.expected_working or 'not required'}
  Constraints: {', '.join(q.student_facing_constraints)}"""
        for q in order.questions
    )

    return f"""You are a question writer, not a lesson planner.

Write exactly the questions specified below.
Do not add questions. Do not remove questions.
Do not change difficulty. Do not change expected answers.
You may reword student-facing question text for clarity,
but the cognitive demand and answer must not change.

QUESTIONS TO WRITE:
{questions_spec}

ANCHOR FACTS (do not change these):
{format_source_of_truth(order.source_of_truth)}

REGISTER:
{order.register.level} · {order.register.tone}
Avoid: {', '.join(order.register.avoid)}

Return JSON: one entry per question_id with student-facing question text.
"""
```

### What it returns

```python
list[GeneratedQuestionBlock]
```

`expected_answer` and `expected_working` are copied from the WorkOrder
directly — never regenerated from prose. The question writer may only
produce the student-facing question text.

### Validation (Level 1)

```
□ Exactly one block per planned question_id — no extras, no missing
□ difficulty preserved from WorkOrder
□ expected_answer unchanged from WorkOrder
□ No additional question_ids in output
```

---

## Step 5 — Visual Executor

**File:** `backend/src/v3_execution/executors/visual_executor.py`
**Prompt:** `backend/src/v3_execution/prompts/visual_executor.py`

Restructures `diagram_generator` in the v3 path.

**SVG generation is not used in the v3 path.** The default visual
executor uses Gemini Imagen via the `google-genai` SDK — same model
and GCS bucket as v2 (`gemini-3.1-flash-image-preview`, `lectio-bucket-1`).
Existing SVG generation capability is not deleted but is not invoked
in the v3 execution path unless explicitly re-enabled later.
The quality bar set in v2 is preserved and extended through the
WorkOrder spec travelling completely into the prompt.

The visual executor does not decide whether a visual is needed.
That decision was made by the Lesson Architect and lives in the
`VisualPlanItem`. The executor renders exactly what it was told.

### Visual modes

```
diagram          → single image, educational diagram
diagram_series   → multiple frames, same anchor, chained context
image            → single image, contextual or real-world
simulation       → routes to existing interaction generator (unchanged)
```

### Single frame prompt

```python
def build_visual_prompt(
    order: VisualGeneratorWorkOrder,
    previous_frame_description: Optional[str] = None
) -> str:
    anchor_block = ""
    if order.visual.uses_anchor_id:
        anchor_block = f"""
ANCHOR FACTS (preserve exactly — do not change dimensions, units, or labels):
{format_anchor_for_visual(order.source_of_truth, order.visual.uses_anchor_id)}
"""

    continuity_block = ""
    if previous_frame_description:
        continuity_block = f"""
VISUAL CONTINUITY:
This image is part of a series. The previous frame showed:
{previous_frame_description}
Keep the same visual style, same shape dimensions, same colour scheme,
same label positions. Only add what is new in this frame.
"""

    return f"""Generate a clear educational diagram for a printed resource.

PURPOSE: {order.visual.purpose}

MUST SHOW:
{chr(10).join(f'- {item}' for item in order.visual.must_show)}

MUST NOT SHOW:
{chr(10).join(f'- {item}' for item in order.visual.must_not_show)}

LABELS REQUIRED: {', '.join(order.visual.labels_required)}
{anchor_block}{continuity_block}
CONSISTENCY LOCKS:
{chr(10).join(f'- {lock}' for lock in order.visual.consistency_locks)}

PRINT REQUIREMENTS:
{chr(10).join(f'- {req}' for req in order.visual.print_requirements)}

Style: clean, educational, suitable for {order.resource_type}.
No decorative elements. No background patterns.
High contrast. Large clear labels.
"""
```

### Diagram series — one call per frame with chained context

For `diagram_series`, the visual executor calls the image generator once
per frame in sequence. Each call receives the previous frame's description
as context so visual consistency is enforced across the series:

```python
async def execute_diagram_series(
    order: VisualGeneratorWorkOrder
) -> list[GeneratedVisualBlock]:
    blocks = []
    previous_description = None

    for i, frame_spec in enumerate(order.visual.frames):
        frame_order = build_frame_order(order, frame_spec, i)
        prompt = build_visual_prompt(frame_order, previous_description)

        image_url = await generate_image(prompt)
        previous_description = frame_spec.description

        blocks.append(GeneratedVisualBlock(
            visual_id=f"{order.visual.id}_frame_{i}",
            attaches_to=order.visual.attaches_to,
            frame_index=i,
            mode="diagram_series",
            image_url=image_url,
            source_work_order_id=order.work_order_id
        ))

    return blocks
```

### Validation (Level 1)

```
□ image_url is a valid GCS URL
□ visual_id matches WorkOrder
□ frame_index present and sequential for diagram_series
□ All frames in a series share the same attaches_to target
```

---

## Step 6 — Answer Key Generator

**File:** `backend/src/v3_execution/executors/answer_key_generator.py`
**Prompt:** `backend/src/v3_execution/prompts/answer_key.py`

New executor. The answer key is an explicit output with its own
contract — not an afterthought appended to question generation.

### What it receives

```
AnswerKeyWorkOrder:
  questions         → QuestionPlanItem list with expected_answer
  answer_key_plan   → style, included question_ids, notes
  source_of_truth   → anchor facts for reference
```

### Key rule

If `expected_answer` and `expected_working` are already in the blueprint
(they always are for deterministic subjects like maths and science),
the answer key generator formats and explains them — it does not
recalculate. For open-ended subjects it may generate explanation prose
around the provided answer.

### Styles

```
answers_only        → question ID + correct answer, no explanation
brief_explanations  → answer + one sentence of reasoning
full_working        → complete step-by-step working shown
```

### Validation (Level 1)

```
□ Every question_id in answer_key_plan.include_question_ids has an entry
□ No extra question_ids appear in output
□ Expected answers match blueprint — not recalculated
□ Style matches answer_key_plan.style
```

---

## Step 7 — Runtime Orchestrator

**File:** `backend/src/v3_execution/runtime/runner.py`
**File:** `backend/src/v3_execution/runtime/events.py`

The runner orchestrates executor parallelism and SSE event emission.
Generation begins immediately after the teacher approves the blueprint
and clicks generate. That is the only safe trigger point — the plan
is fully locked and the teacher knows exactly what is coming.

### No pipeline — async functions only

v3 executors do not use LangGraph or any pipeline framework.

LangGraph was correct for v2 because nodes needed to pass state to each
other — the composition planner needed the curriculum planner's output,
the content generator needed the composition planner's decisions.
State flowed through the graph.

v3 executors need none of that. Every executor receives everything it
needs from its WorkOrder upfront. The blueprint already resolved all
planning state before execution begins. There is no state that needs
to flow between executors.

The runner is therefore plain Python async:

```python
# runner.py — no LangGraph, no pipeline
import asyncio
from v3_execution.executors.section_writer import execute_section
from v3_execution.executors.question_writer import execute_questions
from v3_execution.executors.visual_executor import execute_visual
from v3_execution.executors.answer_key_generator import execute_answer_key
from v3_execution.assembly.section_builder import V3SectionBuilder
from v3_execution.runtime.events import emit


async def run_generation(
    blueprint: ProductionBlueprint,
    work_orders: CompiledWorkOrders,
    emit_event: callable
) -> ExecutionResult:

    result = ExecutionResult(
        generation_id=blueprint.metadata.blueprint_id,
        blueprint_id=blueprint.metadata.blueprint_id
    )

    await emit_event("generation_started", {})

    # Wave 1 — independent tasks, all parallel
    # Section writing, question writing, and blueprint-only visuals
    # share no dependencies — fire all at once

    blueprint_only_visual_orders = [
        v for v in work_orders.visual_orders
        if v.dependency == "blueprint_only"
    ]

    wave_1_results = await asyncio.gather(
        *[execute_section(order, emit_event)
          for order in work_orders.section_orders],
        *[execute_questions(order, emit_event)
          for order in work_orders.question_orders],  # per-section
        *[execute_visual(order, emit_event)
          for order in blueprint_only_visual_orders],
    )

    for r in wave_1_results:
        if isinstance(r, list) and r:
            if isinstance(r[0], GeneratedComponentBlock):
                result.component_blocks.extend(r)
            elif isinstance(r[0], GeneratedQuestionBlock):
                result.question_blocks.extend(r)
            elif isinstance(r[0], GeneratedVisualBlock):
                result.visual_blocks.extend(r)

    # Wave 2 — text-dependent visuals wait for parent sections

    text_dependent_orders = [
        v for v in work_orders.visual_orders
        if v.dependency in ("section_text", "question_text")
    ]

    if text_dependent_orders:
        wave_2_results = await asyncio.gather(*[
            execute_visual(order, emit_event)
            for order in text_dependent_orders
        ])
        for r in wave_2_results:
            result.visual_blocks.extend(r)

    # Wave 3 — answer key waits for questions

    result.answer_key = await execute_answer_key(
        work_orders.answer_key_order, emit_event
    )

    # Assemble — deterministic, no LLM

    await emit_event("assembly_started", {})
    assembler = V3SectionBuilder()
    draft_pack = assembler.build(
        blueprint,
        result.component_blocks,
        result.question_blocks,
        result.visual_blocks,
        manifest=load_manifest()
    )
    await emit_event("draft_pack_ready", {"section_count": len(draft_pack)})

    return result
```

Each executor is a standalone async function — independently testable,
no shared state, no graph traversal:

```python
# section_writer.py
async def execute_section(
    order: SectionWriterWorkOrder,
    emit_event: callable
) -> list[GeneratedComponentBlock]:
    await emit_event("section_writing_started", {"section_id": order.section.id})
    # LLM call → Level 1 validation → single retry on failure
    for block in blocks:
        await emit_event("component_ready", {
            "component_id": block.component_id,
            "section_id": block.section_id,
            "position": block.position,
            "section_field": block.section_field,
            "data": block.data
        })
    return blocks


# question_writer.py
async def execute_questions(
    order: QuestionWriterWorkOrder,
    emit_event: callable
) -> list[GeneratedQuestionBlock]:
    await emit_event("questions_started", {})
    # LLM call → Level 1 validation → single retry on failure
    for block in blocks:
        await emit_event("question_ready", {
            "question_id": block.question_id,
            "section_id": block.section_id,
            "difficulty": block.difficulty
        })
    return blocks


# visual_executor.py
async def execute_visual(
    order: VisualGeneratorWorkOrder,
    emit_event: callable
) -> list[GeneratedVisualBlock]:
    await emit_event("visual_generation_started", {"visual_id": order.visual.id})
    # Imagen call per frame, chained context for series
    for block in blocks:
        await emit_event("visual_ready", {
            "visual_id": block.visual_id,
            "attaches_to": block.attaches_to,
            "frame_index": block.frame_index,
            "image_url": block.image_url
        })
    return blocks
```

This is simpler, faster, and more debuggable than a pipeline.
Each function is independently testable. The runner coordinates
them with standard Python asyncio. No graph traversal, no shared
mutable state, no LangGraph dependency in the execution layer.

### API endpoint

```
POST /api/v1/v3/generate
Body: { "blueprint_id": "...", "generation_id": "..." }
Response: SSE stream
```

### Dependency graph

```
Blueprint approved
        ↓
Compile WorkOrders (deterministic, instant)
        ↓
Wave 1 — asyncio.gather()
┌──────────────────────────────────────┐
│ execute_section() × N sections        │
│ execute_questions()                   │ all parallel
│ execute_visual() × blueprint-only     │
└──────────────────────────────────────┘
        ↓ wave 1 complete
Wave 2 — asyncio.gather()
┌──────────────────────────────────────┐
│ execute_visual() × text-dependent    │ parallel
└──────────────────────────────────────┘
        ↓ wave 2 complete
Wave 3
┌──────────────────────────────────────┐
│ execute_answer_key()                  │
└──────────────────────────────────────┘
        ↓
Assembler — deterministic, no LLM
        ↓
Draft pack ready → Proposal 3 coherence review
```

### SSE events

**File:** `backend/src/v3_execution/runtime/events.py`

```python
# Emitted by runner as executors complete

GENERATION_STARTED = "generation_started"
WORK_ORDERS_COMPILED = "work_orders_compiled"

SECTION_WRITING_STARTED = "section_writing_started"
COMPONENT_READY = "component_ready"          # one per component block

QUESTIONS_STARTED = "questions_started"
QUESTION_READY = "question_ready"            # one per question block

VISUAL_GENERATION_STARTED = "visual_generation_started"
VISUAL_READY = "visual_ready"               # one per visual/frame

ANSWER_KEY_STARTED = "answer_key_started"
ANSWER_KEY_READY = "answer_key_ready"

ASSEMBLY_STARTED = "assembly_started"
DRAFT_PACK_READY = "draft_pack_ready"

COMPONENT_PATCHED = "component_patched"     # from Proposal 3 repair
```

Event payload shapes:

```python
# component_ready
{
  "event": "component_ready",
  "component_id": "worked-example-card",
  "section_id": "section_2",
  "position": 2,
  "section_field": "worked_example",
  "data": { ...component content... }
}

# visual_ready
{
  "event": "visual_ready",
  "visual_id": "l_shape_step_3",
  "attaches_to": "section_2",
  "frame_index": None,         # None for single, int for series frame
  "image_url": "https://storage.googleapis.com/lectio-bucket-1/..."
}

# component_patched (from Proposal 3)
{
  "event": "component_patched",
  "component_id": "worked-example-card",
  "section_id": "section_2",
  "data": { ...corrected content... }
}
```

---

## Step 8 — v3 Assembler

**Files:** `backend/src/v3_execution/assembly/`

The assembler is deterministic. It collects all generated blocks,
maps them to their `section_field` positions using the Lectio manifest,
and builds a `SectionContent`-compatible document in blueprint order.

```python
class V3SectionBuilder:
    def build(
        self,
        blueprint: ProductionBlueprint,
        component_blocks: list[GeneratedComponentBlock],
        question_blocks: list[GeneratedQuestionBlock],
        visual_blocks: list[GeneratedVisualBlock],
        manifest: dict
    ) -> list[SectionContent]:

        sections = []
        for section_plan in sorted(
            blueprint.section_plan, key=lambda s: s.order
        ):
            section_data = {}

            # map component blocks by section_field
            for block in component_blocks:
                if block.section_id == section_plan.id:
                    section_data[block.section_field] = block.data

            # attach questions
            questions = [
                b for b in question_blocks
                if b.section_id == section_plan.id
            ]
            if questions:
                section_data["practice"] = [q.data for q in questions]

            # attach visuals
            visuals = [
                b for b in visual_blocks
                if b.attaches_to == section_plan.id
            ]
            if visuals:
                section_data["diagram"] = visuals[0].image_url
                if len(visuals) > 1:
                    section_data["diagram_series"] = [
                        v.image_url for v in sorted(
                            visuals, key=lambda v: v.frame_index or 0
                        )
                    ]

            sections.append(SectionContent(**section_data))

        return sections
```

Rules:
- Assembler builds in `section_plan.order` always
- Assembler may not reorder sections
- Assembler fails loudly if a required planned block is missing
- Assembler maps `component_id → section_field` via Lectio manifest only
- Assembler must construct valid Lectio-shaped SectionContent fields —
  not raw URLs or raw lists. For example:

  diagram field:
    { "image_url": visual.image_url,
      "caption": visual.caption,
      "alt_text": visual.alt_text }

  practice field:
    { "problems": [q.data for q in questions],
      "label": "Practice Questions" }

  The assembler code samples above are pseudocode. Real implementation
  must match the Lectio component schemas from section-content-schema.json.

---

## Step 9 — Frontend Canvas

**Changes are minimal.** The existing SSE subscription infrastructure
is unchanged. Three additions only.

### Addition 1 — Blueprint-driven skeleton

On blueprint approval the teacher sees a "Generate" button.
On click, the canvas renders immediately with all placeholders
in blueprint order before any SSE events arrive.

The frontend already has the blueprint at this point.
It uses `section_plan` to build the skeleton:

```typescript
// Build skeleton from approved blueprint
function buildCanvasSkeleton(blueprint: ProductionBlueprint): CanvasSection[] {
  return blueprint.section_plan
    .sort((a, b) => a.order - b.order)
    .map(section => ({
      id: section.id,
      title: section.title,
      teacherLabel: section.components.map(c => c.teacher_label).join(' · '),
      components: section.components.map(c => ({
        id: c.component_id,
        teacherLabel: c.teacher_label,
        status: 'pending',
        data: null
      })),
      visual: section.visual.required
        ? { status: 'pending', url: null }
        : null,
      questions: blueprint.question_plan
        .filter(q => q.attaches_to_section_id === section.id)
        .map(q => ({ id: q.id, difficulty: q.difficulty, status: 'pending' }))
    }))
}
```

Skeleton renders instantly on generate click. No waiting.

### Addition 2 — Three new SSE event handlers

Added to the existing SSE subscription:

```typescript
case 'component_ready':
  canvas.fillComponent(
    event.section_id,
    event.component_id,
    event.data
  )
  break

case 'visual_ready':
  canvas.fillVisual(
    event.attaches_to,
    event.image_url,
    event.frame_index
  )
  break

case 'component_patched':
  canvas.patchComponent(
    event.section_id,
    event.component_id,
    event.data
  )
  break
```

### Addition 3 — Subtle patch indicator

When `component_patched` fires, the affected component gets a brief
soft highlight that fades after 2 seconds. No jarring re-render.
A small "refined" label appears and fades. Teacher is aware something
was quietly corrected without being alarmed.

```typescript
function patchComponent(sectionId, componentId, data) {
  fillComponent(sectionId, componentId, data)  // update content
  flashPatchIndicator(sectionId, componentId)   // subtle highlight
}
```

---

## Implementation Order

All steps are sequential. Do not start a step until the previous
one is verified.

```
Step 1 — Generated block models
  Write models.py
  All block types instantiate without error
  source_work_order_id on every type

Step 2 — Executor-level validation
  Write validation.py
  All Level 1 checks implemented
  Retry logic on failure (max 1 retry)
  Warnings collected for Proposal 3

Step 3 — Section writer
  Write section_writer.py + prompt
  Test: given SectionWriterWorkOrder with 3 components,
        returns exactly 3 component blocks
  Test: unplanned component_id in output → rejected
  Test: anchor fact changed → rejected

Step 4 — Question writer
  Write question_writer.py + prompt
  Test: given 3 planned questions, returns exactly 3 blocks
  Test: difficulty preserved
  Test: expected_answer unchanged
  Test: extra question in output → rejected

Step 5 — Visual executor
  Write visual_executor.py + prompt
  SVG generation retired
  Single frame: returns one GeneratedVisualBlock with valid GCS URL
  Diagram series: one call per frame, previous_description chained
  Test: must_show items appear in prompt
  Test: anchor facts travel to prompt unchanged
  Test: frame_index sequential for series

Step 6 — Answer key generator
  Write answer_key_generator.py + prompt
  Test: all planned question_ids have entries
  Test: expected_answers not recalculated
  Test: style matches work order

Step 7 — Runtime orchestrator
  Write runner.py + events.py
  POST /api/v1/v3/generate endpoint
  SSE stream opens on generate click
  Blueprint-only visuals start in parallel with section writing
  Text-dependent visuals wait for parent section
  Answer key waits for questions
  Assembler waits for all required blocks
  All SSE event types emitted correctly

Step 8 — v3 assembler
  Write section_builder.py + pack_builder.py
  Builds in blueprint order always
  Maps component_id → section_field via Lectio manifest
  Fails loudly on missing required block
  Test: approved blueprint → draft pack end-to-end

Step 9 — Frontend canvas
  Build canvas skeleton from blueprint on generate click
  Add component_ready handler
  Add visual_ready handler
  Add component_patched handler with subtle patch indicator
  Test: skeleton renders before first SSE event arrives
  Test: components fill in correct positions regardless of arrival order
```

---

## Non-Negotiable Rules for the Coding Agent

```
1.  All new code lives in backend/src/v3_execution/ and frontend canvas
2.  No v2 pipeline nodes modified. Only app/router registration
    may be touched to mount the POST /api/v1/v3/generate endpoint
3.  No LangGraph in the execution layer — plain Python asyncio only
    Each executor is a standalone async function, not a pipeline node
4.  Every executor prompt must state explicitly: generate only what is
    in the WorkOrder, do not add components, do not change anchor facts
5.  source_work_order_id present on every generated block — no exceptions
6.  SVG generation not used in v3 path — visual executor uses Gemini
    Imagen by default. SVG capability not deleted, just not invoked.
7.  Diagram series: one image generator call per frame with chained context
8.  expected_answer copied from WorkOrder — never regenerated by executor
9.  Assembler builds in section_plan.order always — never reorders
10. Assembler fails loudly on missing required block — no silent skips
11. Level 1 validation runs after every executor call before block accepted
12. Wave 1 (sections + questions + blueprint-only visuals) runs in parallel
    via asyncio.gather() — never sequentially
13. Frontend canvas skeleton renders on generate click before SSE arrives
14. component_patched fires subtle patch indicator — no jarring re-render
```

---

## Definition of Done

Proposal 2 is complete when:

```
1.  models.py defines all block types, CompiledWorkOrders, DraftPack,
    and ExecutorOutcome — all with source_work_order_id on block types
2.  validation.py runs Level 1 checks after every executor call
3.  Question WorkOrders compiled per section (list[QuestionWriterWorkOrder])
    not as one global order
4.  Section writer generates only WorkOrder-planned components
4.  Question writer preserves difficulty and expected_answer from WorkOrder
5.  Visual executor uses Gemini Imagen for all modes — SVG retired
6.  Diagram series uses one call per frame with chained previous context
7.  Answer key generator formats blueprint answers — does not recalculate
8.  Runtime orchestrator uses asyncio.gather() for wave 1 parallelism — not LangGraph
9.  All SSE event types emit with correct payloads
10. POST /api/v1/v3/generate endpoint exists and streams SSE
11. v3 assembler builds SectionContent-compatible draft pack in blueprint order
12. Assembler fails loudly on missing required block
13. Frontend canvas skeleton renders on generate click before first SSE event
14. component_ready fills correct positional placeholder
15. visual_ready fills visual placeholder with correct frame_index for series
16. component_patched applies subtle highlight indicator
17. End-to-end test: approved blueprint → draft pack via v3 path
18. v2 pipeline untouched and still running
```

Final deliverable for Proposal 2:

```
ProductionBlueprint
    ↓
CompiledWorkOrders
    ↓
ExecutorOutcome[] (via asyncio waves)
    ↓
ExecutionResult (GeneratedBlocks aggregated)
    ↓
DraftPack (SectionContent-valid, blueprint-ordered)
    ↓
Ready for Proposal 3 coherence review
```

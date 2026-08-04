# Textbook Generator v3 — Proposal 3: Coherence Reviewer

## Purpose

Proposal 2 delivered the execution layer: WorkOrders → GeneratedBlocks →
DraftPack. The draft pack exists but has not been verified against the
approved plan.

Proposal 3 delivers the coherence reviewer: a blueprint-aware quality
system that checks whether the generated draft pack obeyed the approved
Production Blueprint, produces a structured report, routes repair targets
back to the correct Proposal 2 executors, and finalises the resource only
when blocking issues are resolved.

**Scope:** Coherence reviewer · Deterministic checks · LLM judgment review ·
CoherenceReport model · RepairTarget model · Surgical repair router ·
SSE review events · Generation report integration

**Out of scope:** Frontend brief builder collapse · Staging environment ·
New component types · Blueprint changes (plan is locked before this runs)

**Prerequisite:** Proposal 2 complete and verified. `DraftPack` producing
valid `SectionContent`-compatible output. All SSE events from Proposal 2
emitting correctly. `source_work_order_id` present on every generated block.

**Codebase:** Textbook Generator backend only. No Lectio changes.
No v2 pipeline nodes modified. Shared routing, event registration,
and report writing may be extended only through v3-safe paths.

---

## The Reviewer's Single Question

The coherence reviewer does not ask:

```
"Is this generally a good lesson?"
```

It asks:

```
"Did the generated pack obey the approved blueprint?"
```

That is the only question. The blueprint was approved by the teacher.
The reviewer enforces it. It does not redesign, improve, or expand.

---

## Backend File Structure

All new code lives in `backend/src/v3_review/`.

```
backend/src/v3_review/
  __init__.py
  models.py                  # CoherenceReport, RepairTarget, ReviewIssue
  deterministic_checks.py    # code checks — no LLM
  llm_review.py              # LLM judgment checks
  reviewer.py                # orchestrates both phases
  repair_router.py           # routes RepairTargets to correct executor
  prompts.py                 # LLM reviewer prompt builder
```

---

## Step 1 — Data Contracts

**File:** `backend/src/v3_review/models.py`

### ReviewIssue

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field

Severity = Literal["minor", "major", "blocking"]

RepairExecutor = Literal[
    "section_writer",
    "question_writer",
    "visual_executor",
    "answer_key_generator",
    "assembler"
]

IssueCategory = Literal[
    "missing_planned_content",
    "extra_unplanned_content",
    "anchor_drift",
    "visual_mismatch",
    "question_mismatch",
    "answer_key_mismatch",
    "register_mismatch",
    "practice_progression_mismatch",
    "internal_artifact_leak",
    "schema_violation",
    "print_risk"
]


class ReviewIssue(BaseModel):
    issue_id: str
    severity: Severity
    category: IssueCategory
    message: str
    blueprint_ref: Optional[str] = None   # which blueprint field was violated
    generated_ref: Optional[str] = None   # which generated block is affected
    suggested_repair_executor: RepairExecutor
    repair_target_id: Optional[str] = None
```

### RepairTarget

```python
class RepairTarget(BaseModel):
    target_id: str
    executor: RepairExecutor
    source_work_order_id: Optional[str] = None  # from GeneratedBlock
    target_type: Literal[
        "section_component",
        "question",
        "visual",
        "answer_key",
        "assembly"
    ]
    target_ref: str              # human-readable e.g. "section_2.worked_example"
    # structured refs — apply_repair() uses these, not target_ref string parsing
    section_id: Optional[str] = None
    component_id: Optional[str] = None
    question_id: Optional[str] = None
    visual_id: Optional[str] = None
    reason: str
    constraints: list[str] = Field(default_factory=list)
    severity: Severity
```

### CoherenceReport

```python
class CoherenceReport(BaseModel):
    blueprint_id: str
    generation_id: str
    status: Literal[
        "passed",               # no blocking or major issues
        "passed_with_warnings", # minor issues only
        "repair_required",      # blocking or major issues with repair targets
        "failed",               # blocking issue with no repair target
        "escalated"             # repairs exhausted after 2 attempts
    ]
    deterministic_passed: bool
    llm_review_passed: bool
    blocking_count: int = 0
    major_count: int = 0
    minor_count: int = 0
    issues: list[ReviewIssue] = Field(default_factory=list)
    repair_targets: list[RepairTarget] = Field(default_factory=list)
    repaired_target_ids: list[str] = Field(default_factory=list)
    repair_attempts: dict[str, int] = Field(default_factory=dict)
    # tracks attempt count per target_id across the report
```

### RepairOutcome

```python
class RepairOutcome(BaseModel):
    target_id: str
    ok: bool
    attempt: int              # 1 or 2 — max 2 attempts per target
    new_block: Optional[dict] = None
    errors: list[str] = Field(default_factory=list)
```

**Verification:**
```
□ All models import and instantiate without error
□ RepairTarget.source_work_order_id links to Proposal 2 block traceability
□ CoherenceReport.status derives correctly from blocking/major counts
□ RepairOutcome.attempt capped at 2 — no infinite repair loops
```

---

## Step 2 — Deterministic Checks

**File:** `backend/src/v3_review/deterministic_checks.py`

Deterministic checks run first. They are code checks — no LLM,
no opinion, no judgment. Fast, cheap, and reliable.

### Check functions

Each function takes `blueprint` and `draft_pack` and returns
`list[ReviewIssue]`. Keep them small and independently testable.

```python
def check_planned_sections_exist(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack
) -> list[ReviewIssue]: ...
# Blocking if any planned section_id is absent from draft_pack.sections

def check_no_extra_sections(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack
) -> list[ReviewIssue]: ...
# Blocking if draft_pack contains section_id not in blueprint.section_plan

def check_planned_components_exist(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack
) -> list[ReviewIssue]: ...
# Blocking if any planned component_id absent from its section

def check_planned_questions_exist(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack
) -> list[ReviewIssue]: ...
# Blocking if any planned question_id absent from draft_pack

def check_no_extra_questions(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack
) -> list[ReviewIssue]: ...
# Major if draft_pack contains question_id not in blueprint.question_plan

def check_planned_visuals_exist(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack
) -> list[ReviewIssue]: ...
# Blocking if any section with visual.required=true has no visual attached

def check_visuals_attach_to_valid_targets(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack
) -> list[ReviewIssue]: ...
# Blocking if visual.attaches_to references non-existent section/question

def check_answer_key_entries(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack
) -> list[ReviewIssue]: ...
# Blocking if any answer_key_plan.include_question_ids entry is missing

def check_expected_answers_preserved(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack
) -> list[ReviewIssue]: ...
# Blocking if any generated answer differs from blueprint.expected_answer

def check_anchor_facts(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack
) -> list[ReviewIssue]: ...
# Blocking if anchor dimensions/units/final answer differ from SourceOfTruth

def check_internal_artifact_leaks(
    draft_pack: DraftPack
) -> list[ReviewIssue]: ...
# Blocking — scans student-facing text for:
# section IDs, work_order_ids, source_work_order_ids,
# "undefined", "null", "TODO", "[object Object]", "NaN",
# any UUIDs or technical internal identifiers

def check_lectio_schema_validity(
    draft_pack: DraftPack,
    manifest: dict
) -> list[ReviewIssue]: ...
# Blocking if any component data fails Lectio component schema validation
# Uses section-content-schema.json from Lectio contracts

def check_component_ids_in_manifest(
    draft_pack: DraftPack,
    manifest: dict
) -> list[ReviewIssue]: ...
# Blocking if any component_id in draft_pack not found in Lectio manifest
```

### Anchor fact checking — detail

`SourceOfTruth` in the blueprint contains exact anchor facts:

```json
{
  "anchor_examples": [{
    "id": "anchor_l_shape_01",
    "facts": {
      "outer_width": "10 cm",
      "outer_height": "6 cm",
      "cutout_width": "4 cm",
      "cutout_height": "3 cm",
      "total_area": "48 sq cm"
    },
    "do_not_change": ["units", "dimensions", "final answer"]
  }]
}
```

The anchor checker scans generated text, question data, visual captions,
alt text, answer key entries, and structured metadata for these values
using string matching on fact values.

**Honest scope:** This checker operates on structured fields and text only.
It does not inspect image pixels — if a visual visually shows wrong
dimensions but the caption is correct, this check will not catch it.
Visual-semantic drift is handled by the LLM judgment reviewer using
captions and metadata. Future multimodal visual QC is out of scope for v3.

It still catches the real failure cases from v2:

```
Text says total area = 48 sq cm,
diagram caption says 54 sq cm → blocking anchor_drift

Visual 1 uses cm, Visual 3 uses ft → blocking anchor_drift

Anchor outer height changes from 6 cm to 8 cm across series → blocking

Answer key answer differs from blueprint expected_answer → blocking
```

### Internal artifact leak check — pattern list

Scan **student-facing text fields only** — rendered question text,
explanation prose, worked example steps, pitfall alerts, answer key
student-visible text. Never scan internal metadata fields, block IDs,
or work order references — those legitimately contain these patterns.

Student-facing fields to scan:

```python
LEAK_PATTERNS = [
    r"section-[a-f0-9]{8}",     # section IDs
    r"wo_[a-z_]+_\d+",          # work order IDs
    r"anchor_[a-z_]+_\d+",      # anchor IDs
    r"\bundefined\b",
    r"\bnull\b",
    r"\bTODO\b",
    r"\[object Object\]",
    r"\bNaN\b",
    r"source_work_order_id",
    r"component_id",
    r"blueprint_id",
    r"generation_id",
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    # UUID pattern
]
```

**Verification checklist for deterministic checks:**
```
□ Missing planned section → blocking issue emitted
□ Extra unplanned section → blocking issue emitted
□ Anchor outer height changed → blocking anchor_drift emitted
□ Answer 54 sq cm when blueprint says 48 sq cm → blocking emitted
□ Missing required visual → blocking emitted
□ section-338cd019 in student text → blocking internal_artifact_leak
□ Component ID not in Lectio manifest → blocking schema_violation
□ All checks return list[ReviewIssue] (empty list if no issues)
□ All checks independently testable with fixture blueprints + packs
```

---

## Step 3 — LLM Judgment Review

**File:** `backend/src/v3_review/llm_review.py`
**File:** `backend/src/v3_review/prompts.py`

Runs after deterministic checks. Only if deterministic checks produce
no blocking issues (or blocking issues are already targeted for repair).

The LLM reviewer only reviews and reports. It never rewrites content.

### What the LLM reviewer receives

The LLM reviewer receives a compressed view — not raw giant documents.
Since SVG is not used in v3, no image data is sent. Only text-derivable
metadata travels to the reviewer:

```python
def build_llm_review_input(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack,
    deterministic_issues: list[ReviewIssue]
) -> dict:
    return {
        "blueprint_summary": {
            "lesson_mode": blueprint.lesson_intent.lesson_mode,
            "lenses": [l.id for l in blueprint.lenses],
            "register": blueprint.register.dict(),
            "learner_profile": blueprint.learner_profile.dict(),
            "support_adaptations": [s.id for s in blueprint.support_adaptations],
            "question_plan": [
                {"id": q.id, "difficulty": q.difficulty,
                 "scaffolding": q.scaffolding}
                for q in blueprint.question_plan
            ],
            "visual_strategy": blueprint.visual_strategy.global_strategy,
            "consistency_rules": [r.rule for r in blueprint.consistency_rules]
        },
        "section_summaries": [
            {
                "id": s.section_id,
                "components": [b.component_id for b in
                               get_section_blocks(draft_pack, s.section_id)],
                "text_sample": extract_text_sample(draft_pack, s.section_id)
            }
            for s in draft_pack.sections
        ],
        "question_list": [
            {"id": q.question_id, "difficulty": q.difficulty,
             "text_sample": q.data.get("question_text", "")[:200]}
            for q in draft_pack_questions(draft_pack)
        ],
        "visual_metadata": [
            {"id": v.visual_id, "caption": v.caption,
             "alt_text": v.alt_text, "mode": v.mode}
            for v in draft_pack_visuals(draft_pack)
        ],
        "answer_key_summary": summarise_answer_key(draft_pack),
        "deterministic_issues": [i.dict() for i in deterministic_issues]
    }
```

### LLM judgment checks

```python
LLM_CHECKS = [
    "Does the register match the blueprint specification?",
    "Does the practice progression match the blueprint question plan?",
    "Does the visual support the intended thinking move for its section?",
    "Does the explanation target the intended learner profile?",
    "For repair lessons: does the content stay focused on the fault line?",
    "Are supports applied as planned in support_adaptations?",
    "Are questions appropriately scaffolded per the blueprint?",
    "Does the resource structure match the planned resource_type?"
]
```

### Prompt rule — enforced in system prompt

```
You are a coherence reviewer, not a lesson designer.

Review the generated draft pack against the approved Production Blueprint.
Do not suggest improvements beyond what the blueprint requires.
Do not redesign the lesson.
Do not add sections, questions, or visuals that are not in the blueprint.

For each issue you identify, state:
- The specific blueprint field that was not followed
- The specific generated content that failed to follow it
- The severity (minor / major / blocking)
- The correct executor to fix it

Return a JSON array of ReviewIssue objects. Return an empty array if
no issues are found. Do not return prose.
```

### Output

```python
list[ReviewIssue]
```

Structured only. No prose. Validated against `ReviewIssue` schema
before being accepted into the `CoherenceReport`.

**Verification checklist:**
```
□ LLM reviewer returns structured ReviewIssue[] not prose
□ LLM reviewer identifies register too formal for EAL class
□ LLM reviewer identifies practice jumping warm → cold too quickly
□ LLM reviewer identifies repair lesson accidentally reteaching whole topic
□ LLM reviewer does NOT suggest new sections not in blueprint
□ LLM reviewer does NOT redesign or improve the lesson
□ No image data sent to LLM reviewer — captions and metadata only
```

---

## Step 4 — Reviewer Orchestrator

**File:** `backend/src/v3_review/reviewer.py`

Orchestrates both phases and produces the final `CoherenceReport`.

```python
async def run_coherence_review(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack,
    manifest: dict,
    emit_event: callable
) -> CoherenceReport:

    await emit_event("coherence_review_started", {})

    # Phase 1 — deterministic checks
    await emit_event("deterministic_review_started", {})

    det_issues = []
    det_issues += check_planned_sections_exist(blueprint, draft_pack)
    det_issues += check_no_extra_sections(blueprint, draft_pack)
    det_issues += check_planned_components_exist(blueprint, draft_pack)
    det_issues += check_planned_questions_exist(blueprint, draft_pack)
    det_issues += check_no_extra_questions(blueprint, draft_pack)
    det_issues += check_planned_visuals_exist(blueprint, draft_pack)
    det_issues += check_visuals_attach_to_valid_targets(blueprint, draft_pack)
    det_issues += check_answer_key_entries(blueprint, draft_pack)
    det_issues += check_expected_answers_preserved(blueprint, draft_pack)
    det_issues += check_anchor_facts(blueprint, draft_pack)
    det_issues += check_internal_artifact_leaks(draft_pack)
    det_issues += check_lectio_schema_validity(draft_pack, manifest)
    det_issues += check_component_ids_in_manifest(draft_pack, manifest)

    await emit_event("deterministic_review_complete", {
        "issue_count": len(det_issues),
        "blocking": sum(1 for i in det_issues if i.severity == "blocking")
    })

    # Phase 2 — LLM judgment review
    # Gate: skip if draft is structurally too broken to summarise safely
    det_blocking = [i for i in det_issues if i.severity == "blocking"]
    schema_failures = [
        i for i in det_issues if i.category == "schema_violation"
    ]
    missing_sections = [
        i for i in det_issues if i.category == "missing_planned_content"
        and "section" in i.message.lower()
    ]

    skip_llm = (
        len(det_blocking) > 5
        or len(schema_failures) > 2
        or len(missing_sections) > 1
    )

    if skip_llm:
        await emit_event("llm_review_skipped", {
            "reason": "Deterministic failures too severe — repair first"
        })
        llm_issues = []
    else:
        await emit_event("llm_review_started", {})
        llm_issues = await run_llm_review(blueprint, draft_pack, det_issues)
        await emit_event("llm_review_complete", {
            "issue_count": len(llm_issues)
        })

    all_issues = det_issues + llm_issues
    repair_targets = build_repair_targets(all_issues, draft_pack)

    blocking = [i for i in all_issues if i.severity == "blocking"]
    major = [i for i in all_issues if i.severity == "major"]
    minor = [i for i in all_issues if i.severity == "minor"]

    if not blocking and not major and not minor:
        status = "passed"
    elif not blocking and not major:
        status = "passed_with_warnings"
    elif (blocking or major) and repair_targets:
        status = "repair_required"
    else:
        status = "failed"

    report = CoherenceReport(
        blueprint_id=blueprint.metadata.blueprint_id,
        generation_id=draft_pack.generation_id,
        status=status,
        deterministic_passed=not any(
            i.severity == "blocking" for i in det_issues
        ),
        llm_review_passed=not any(
            i.severity == "blocking" for i in llm_issues
        ),
        blocking_count=len(blocking),
        major_count=len(major),
        minor_count=len(
            [i for i in all_issues if i.severity == "minor"]
        ),
        issues=all_issues,
        repair_targets=repair_targets
    )

    await emit_event("coherence_report_ready", {
        "status": status,
        "blocking_count": report.blocking_count,
        "repair_target_count": len(repair_targets)
    })

    return report
```

---

## Step 5 — Repair Router

**File:** `backend/src/v3_review/repair_router.py`

Routes each `RepairTarget` to the correct Proposal 2 executor,
regenerates only that target, then re-runs only the checks that
touch the repaired block.

### Repair policy

```
blocking → must repair, up to 2 attempts per target
major    → repair if within attempt budget
minor    → log, proceed without repair

If attempt 2 fails on a blocking target → escalate to teacher
Never full regeneration unless teacher explicitly requests it
```

### Repair loop

```python
async def route_repairs(
    report: CoherenceReport,
    blueprint: ProductionBlueprint,
    work_orders: CompiledWorkOrders,
    draft_pack: DraftPack,
    emit_event: callable
) -> tuple[DraftPack, CoherenceReport]:

    targets_to_repair = [
        t for t in report.repair_targets
        if t.severity in ("blocking", "major")
    ]

    for target in targets_to_repair:
        await emit_event("repair_started", {
            "target_id": target.target_id,
            "executor": target.executor,
            "reason": target.reason
        })

        outcome = await dispatch_repair(target, blueprint, work_orders)

        if outcome.ok:
            draft_pack = apply_repair(draft_pack, target, outcome)
            report.repaired_target_ids.append(target.target_id)

            # re-run only checks that touch the repaired block
            recheck_issues = await recheck_target(
                target, blueprint, draft_pack
            )

            if any(i.severity == "blocking" for i in recheck_issues):
                if outcome.attempt < 2:
                    # retry once
                    outcome = await dispatch_repair(
                        target, blueprint, work_orders, attempt=2
                    )
                else:
                    # escalate — do not loop further
                    await emit_event("repair_escalated", {
                        "target_id": target.target_id,
                        "reason": "Two attempts failed"
                    })

            await emit_event("component_patched", {
                "target_ref": target.target_ref,
                "target_type": target.target_type
            })

        else:
            await emit_event("repair_failed", {
                "target_id": target.target_id
            })

    # Final lightweight deterministic safety gate
    # Runs after all repairs — no LLM, cheap structural checks only
    final_issues = []
    final_issues += check_planned_sections_exist(blueprint, draft_pack)
    final_issues += check_planned_components_exist(blueprint, draft_pack)
    final_issues += check_planned_questions_exist(blueprint, draft_pack)
    final_issues += check_planned_visuals_exist(blueprint, draft_pack)
    final_issues += check_expected_answers_preserved(blueprint, draft_pack)

    remaining_blocking = [
        i for i in final_issues if i.severity == "blocking"
        and i.repair_target_id not in report.repaired_target_ids
    ]

    if remaining_blocking:
        report.status = "escalated"
        await emit_event("repair_escalated", {
            "reason": "Blocking issues remain after all repairs"
        })
    else:
        report.status = (
            "passed" if not report.major_count and not report.minor_count
            else "passed_with_warnings" if not report.blocking_count
            else "passed_with_warnings"
        )
        await emit_event("resource_finalised", {
            "status": report.status
        })

    return draft_pack, report
```

### Re-check scope — not full review

After a repair, only the checks relevant to the repaired block re-run.
The full coherence review does not restart.

```python
RECHECK_MAP = {
    "section_component": [
        check_planned_components_exist,
        check_anchor_facts,
        check_internal_artifact_leaks,
        check_lectio_schema_validity
    ],
    "question": [
        check_planned_questions_exist,
        check_expected_answers_preserved,
        check_anchor_facts
    ],
    "visual": [
        check_planned_visuals_exist,
        check_visuals_attach_to_valid_targets,
        check_anchor_facts
    ],
    "answer_key": [
        check_answer_key_entries,
        check_expected_answers_preserved
    ],
    "assembly": [
        check_planned_sections_exist,
        check_planned_components_exist
    ]
}
```

This prevents infinite loops and keeps repair fast.

### Repair target examples

**Bad visual:**
```json
{
  "target_id": "repair_visual_anchor_step_2",
  "executor": "visual_executor",
  "source_work_order_id": "wo_visual_002",
  "target_type": "visual",
  "target_ref": "visuals.anchor_step_2_missing_sides",
  "severity": "blocking",
  "reason": "Visual changed anchor outer height from 6 cm to 8 cm.",
  "constraints": [
    "Reuse anchor_l_shape_01",
    "outer_height must remain 6 cm",
    "unit must remain cm"
  ]
}
```

**Bad section prose:**
```json
{
  "target_id": "repair_section_1_explanation",
  "executor": "section_writer",
  "source_work_order_id": "wo_section_001",
  "target_type": "section_component",
  "target_ref": "section_1.explanation",
  "severity": "major",
  "reason": "Register too formal for below-average Year 8 EAL class.",
  "constraints": [
    "Use short sentences",
    "Define key terms before use",
    "Avoid idioms"
  ]
}
```

**Bad answer key:**
```json
{
  "target_id": "repair_answer_key_q3",
  "executor": "answer_key_generator",
  "source_work_order_id": "wo_answer_key_001",
  "target_type": "answer_key",
  "target_ref": "answer_key.q3",
  "severity": "blocking",
  "reason": "Answer key gives 54 sq cm, blueprint expected 48 sq cm.",
  "constraints": [
    "Expected answer must be 48 sq cm",
    "Use anchor example dimensions exactly"
  ]
}
```

**Verification checklist:**
```
□ visual issue → visual_executor
□ question issue → question_writer
□ answer key issue → answer_key_generator
□ section prose issue → section_writer
□ assembly issue → assembler
□ Max 2 attempts per target enforced — no infinite loops
□ Re-check runs only RECHECK_MAP checks for that target type
□ Full review does not restart after repair
□ component_patched SSE event fires after successful repair
□ repair_escalated SSE event fires after 2 failed attempts
```

---

## Step 6 — SSE Events for Review Phase

These extend the SSE stream from Proposal 2.
Proposal 2 ended with `draft_pack_ready`. Proposal 3 continues from there.

**File:** `backend/src/v3_review/` (add to Proposal 2's events.py)

```python
# Review phase events
COHERENCE_REVIEW_STARTED = "coherence_review_started"
LLM_REVIEW_SKIPPED = "llm_review_skipped"       # severe det failures
DETERMINISTIC_REVIEW_STARTED = "deterministic_review_started"
DETERMINISTIC_REVIEW_COMPLETE = "deterministic_review_complete"
LLM_REVIEW_STARTED = "llm_review_started"
LLM_REVIEW_COMPLETE = "llm_review_complete"
COHERENCE_REPORT_READY = "coherence_report_ready"

# Repair events
REPAIR_STARTED = "repair_started"
COMPONENT_PATCHED = "component_patched"   # already defined in Proposal 2
REPAIR_FAILED = "repair_failed"
REPAIR_ESCALATED = "repair_escalated"

# Finalisation
RESOURCE_FINALISED = "resource_finalised"
```

### Teacher-facing progress messages

The frontend shows human-readable states, not technical event names:

```
draft_pack_ready              → "Checking consistency..."
deterministic_review_complete → "Checking diagrams and answers..."
llm_review_complete           → "Reviewing lesson quality..."
repair_started                → "Refining [N] issue(s)..."
component_patched             → (subtle highlight on affected component)
resource_finalised            → "Resource ready"
```

Never expose issue counts, severity levels, or technical repair detail
to the teacher during generation. Those appear in the generation report only.

---

## Step 7 — Generation Report Integration

The generation report (already implemented as per-generation JSON reports
with per-node latency, token counts, cost) gains a new `coherence_review`
section:

```json
{
  "coherence_review": {
    "status": "partial",
    "deterministic_passed": true,
    "llm_review_passed": false,
    "blocking_count": 0,
    "major_count": 1,
    "minor_count": 2,
    "repairs_attempted": 1,
    "repairs_succeeded": 1,
    "issues": [
      {
        "category": "register_mismatch",
        "severity": "major",
        "message": "Register too formal for EAL learners",
        "repaired": true
      }
    ],
    "checks": {
      "planned_sections": "passed",
      "planned_questions": "passed",
      "planned_visuals": "passed",
      "anchor_facts": "passed",
      "answer_key": "passed",
      "register": "repaired",
      "practice_progression": "warning"
    }
  }
}
```

This gives visibility into exactly what the reviewer caught and what
was repaired — the observability that was missing in v2.

---

## Implementation Order

All steps are sequential.

```
Step 1 — Data contracts
  Write CoherenceReport, RepairTarget, ReviewIssue, RepairOutcome
  All models validate without error
  RepairTarget links via source_work_order_id to Proposal 2 blocks

Step 2 — Deterministic checks
  Write all 13 check functions in deterministic_checks.py
  Each function independently testable with fixture data
  Write fixture blueprints and draft packs for all test cases
  All acceptance tests pass (see below)

Step 3 — LLM judgment review
  Write llm_review.py and prompts.py
  Compressed input builder — no image data, captions and metadata only
  Structured ReviewIssue[] output validated before acceptance
  LLM reviewer prompt enforces: review only, no redesign
  Acceptance tests with fixture outputs pass

Step 4 — Reviewer orchestrator
  Write reviewer.py
  Runs deterministic then LLM in sequence
  Produces CoherenceReport from combined issues
  Emits SSE events at each phase boundary

Step 5 — Repair router
  Write repair_router.py
  Routes each RepairTarget to correct Proposal 2 executor
  Max 2 attempts per target enforced
  Re-check runs RECHECK_MAP checks only — not full review
  component_patched SSE event fires after successful repair
  repair_escalated fires after 2 failures

Step 6 — SSE review events
  Add review phase event constants to Proposal 2 events.py
  Teacher-facing progress messages defined
  resource_finalised fires as last event in stream

Step 7 — Generation report integration
  Add coherence_review block to generation report JSON
  Per-check pass/fail/repaired/warning status recorded
```

---

## Acceptance Tests

### Deterministic tests

```
Given blueprint has 4 planned sections and draft has 3:
  → blocking missing_planned_content emitted

Given blueprint anchor says 48 sq cm and draft says 54 sq cm:
  → blocking anchor_drift emitted

Given blueprint requires visual q1_diagram and draft lacks it:
  → blocking missing_planned_content emitted

Given draft contains "section-338cd019" in student-facing text:
  → blocking internal_artifact_leak emitted

Given answer key expected q2 = 68 m² and generated says 70 m²:
  → blocking answer_key_mismatch emitted

Given component_id "worked-example-card" not in Lectio manifest:
  → blocking schema_violation emitted

Given draft has extra question not in blueprint question_plan:
  → major extra_unplanned_content emitted
```

### LLM judgment tests

```
Given register is too formal for EAL learners:
  → major register_mismatch emitted, executor = section_writer

Given practice jumps warm → cold with no medium:
  → major practice_progression_mismatch emitted

Given repair lesson reteaches full topic not just fault line:
  → major register_mismatch or practice_progression_mismatch emitted

Given visual caption describes correct anchor shape and dimensions:
  → no issue emitted (reviewer does not redesign)
```

### Repair routing tests

```
visual issue → executor = visual_executor
question issue → executor = question_writer
answer key issue → executor = answer_key_generator
section prose issue → executor = section_writer
assembly issue → executor = assembler

After repair: re-check runs RECHECK_MAP checks only
After 2 failed attempts: repair_escalated event fires, loop stops
```

### End-to-end test

```
DraftPack with one anchor drift (6 cm → 8 cm in worked example)
  → deterministic_check detects anchor_drift
  → RepairTarget created for section_writer
  → repair_router dispatches to section_writer
  → section re-generated with correct anchor facts
  → recheck passes
  → component_patched event fires
  → CoherenceReport.status = "passed"
  → resource_finalised event fires
```

---

## Non-Negotiable Rules for the Coding Agent

```
1.  All new code lives in backend/src/v3_review/
2.  No v2 pipeline nodes modified. Shared routing and report writing
    may be extended only through v3-safe paths.
3.  Deterministic checks always run before LLM review — no exceptions
4.  LLM review is skipped when blocking deterministic count > 5,
    schema violations > 2, or multiple sections missing
5.  LLM reviewer returns structured ReviewIssue[] only — no prose
6.  LLM reviewer prompt must state: review against blueprint,
    do not redesign, do not add unplanned content
7.  No image data or image URLs sent to LLM reviewer —
    captions, alt text, and metadata only
8.  Internal artifact leak check scans student-facing text only —
    never internal metadata fields
9.  RepairTarget uses structured fields (section_id, component_id,
    question_id, visual_id) — apply_repair() never parses target_ref strings
10. repair_attempts tracked in CoherenceReport.repair_attempts dict
11. Max 2 repair attempts per target — enforced in code, not just prompt
12. Re-check after repair runs RECHECK_MAP checks only — not full review
13. Final lightweight deterministic gate runs after all repairs —
    before resource_finalised fires
14. status uses 5-value lifecycle: passed / passed_with_warnings /
    repair_required / failed / escalated
15. Teacher-facing SSE messages are human-readable — no technical detail
16. component_patched fires subtle frontend highlight (Proposal 2 handler)
17. Generation report records per-check outcomes for every generation
```

---

## Definition of Done

Proposal 3 is complete when:

```
1.  v3_review module exists with all files
2.  CoherenceReport uses 5-value status lifecycle
3.  CoherenceReport.repair_attempts tracks attempt count per target_id
4.  RepairTarget has structured fields: section_id, component_id,
    question_id, visual_id — apply_repair() uses these not string parsing
5.  All 13 deterministic check functions exist and are independently testable
6.  All deterministic acceptance tests pass with fixture data
7.  LLM review skipped when blocking > 5, schema violations > 2,
    or multiple sections missing — llm_review_skipped event fires
8.  LLM reviewer returns structured ReviewIssue[] validated against schema
9.  LLM reviewer does not suggest unplanned content in any test case
10. Internal artifact leak check scans student-facing text only —
    confirmed via test with internal field containing anchor_ pattern
11. Anchor fact checking scoped to structured fields and text —
    comments in code acknowledge image pixel checking is out of scope
12. Reviewer orchestrator runs deterministic then conditional LLM
    and produces CoherenceReport correctly
13. Repair router routes issues to correct executor per target_type
14. Max 2 attempts per target enforced — escalated status set on failure
15. Re-check after repair runs RECHECK_MAP only — confirmed via test
16. Final lightweight deterministic gate runs after all repairs complete
17. resource_finalised fires only after final gate passes
18. All SSE review events emit at correct phase boundaries
19. Generation report includes coherence_review block with per-check outcomes
20. End-to-end test: anchor drift detected → repair_required →
    repaired → final gate passes → resource_finalised
21. v2 pipeline untouched and still running
```

---

## What Proposal 3 Unlocks

After Proposal 3 is complete the full v3 backend pipeline is working:

```
Teacher input
    ↓ Proposal 1
Signal Extractor → Clarification → Lesson Architect → Blueprint
    ↓ Proposal 2
WorkOrders → Executors → DraftPack
    ↓ Proposal 3
Coherence Reviewer → Repairs → Finalised Resource
```

Proposal 4 (frontend collapse and blueprint approval UI) and
Proposal 5 (staging and switchover) can then proceed.

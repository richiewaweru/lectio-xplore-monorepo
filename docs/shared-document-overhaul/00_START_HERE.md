# Lectio Shared Document Overhaul — Start Here

## Purpose

This pack guides the clean-cut transition from path-specific ordinary lesson authoring to one shared authored lesson:

```text
Unit / PathLesson
      ↓
Preparation
      ↓
Structural Plan
      ↓
Enriched Teaching Plan
      ↓
Teacher Approval
      ↓
Shared Document Generation
      ↓
SharedLessonDocument
      ↓
  ┌───┴───┐
  ↓       ↓
Learn    Print
  ↓       ↓
Publish  PDF
```

Core product rule:

> **Plan once. Approve once. Author ordinary lesson content once. Validate once. Realize twice.**

Core operational rule:

> **Every durable generation artifact uses the same mechanics: source-hash verification, idempotent admission, durable run/work-item state, leases/fencing, bounded provider calls, compatible checkpoints, typed failures, targeted retries, validation, output hashing, and atomic final success commit.**

## Baseline

Prepared against current `main` after V3 retirement:

- Repository: `richiewaweru/lectio-xplore-monorepo`
- Observed baseline SHA: `d75d19125dfd6c849c5363b63f0269074faf53d1`
- The old Stage-2 section writer / expander / assembler / retry architecture is retired.
- Current truthful ownership is under `application/`, `curriculum/`, `document/`, `infra/`, `media/`, `learn/`, and `print/`.
- Some V2/V3 names remain in compatibility/configuration code; they are not authority for new architecture.

At execution start, record the real current `main` SHA and DB migration head. If the repo has materially drifted, reconcile the pack with current truth before code changes.

## Clean-cut policy

This is not a backwards-compatibility project.

Temporary parallel implementation is allowed only to prove the replacement. Once a replacement phase passes:

1. route current product creation through the replacement;
2. prove zero current callers of the superseded code;
3. delete that code, prompts, routes, adapters, tests and state handling;
4. add architecture guards so it cannot return.

Do not distort the target architecture merely to read or generate obsolete formats.

## LLM policy

Reuse the existing model abstraction:

```text
ModelSlot.FAST
ModelSlot.STANDARD
ModelSlot.PREMIUM
```

and existing structured-provider / AuthoringEngine infrastructure.

Do not introduce a second model router. New capability names may replace historical V2/V3 capability names, but the slot/spec/provider abstraction remains.

## Reading order

Read numbered files in order. Execution is controlled by:

- `29_PHASED_IMPLEMENTATION_PLAN.md`
- `30_RUNBOOK.md`
- `32_KICKOFF_PROMPT.md`
- `33_SOL_LUNA_OPERATING_CONTRACT.md`

Contracts and machine-readable references live under `contracts/`, `matrices/`, and `checklists/`.

## Completion definition

The program is complete only when a new engineer can explain current lesson generation as:

```text
Preparation → Teaching Plan → SharedLessonDocument → Learn / Print
```

without needing V1/V2/V3 history.

# Phase 02 Resolved Architecture

## Executive summary

Patch 01 solved entry. Phase 02 solves completion.

The native implementation already persists teaching plans, form plans, block results, events, and the final document. The remaining defect is orchestration: approval still runs the back half inline; writers are serial; one block exception aborts the batch; resume does not skip saved work; and assembly depends on an in-memory result list.

Phase 02 converts those foundations into one durable native execution engine.

## Current flow

```text
POST approve teaching
        ├── save approval
        ├── run form planner
        ├── write every block serially
        ├── assemble from local writer_results
        └── return after completion
```

Failure consequences:

```text
request disconnect → execution may stop
block 4 fails      → blocks 5–10 never run
backend restarts   → ready blocks are ignored and rerun
resume assembles   → DB has results, local list does not
```

## Target flow

```text
POST approve teaching
        ├── save approval
        ├── status = queued
        └── return 202
                 │
                 ▼
        DB-leased worker
                 ▼
          load checkpoint
                 ▼
          form plan exists?
          ├── yes: reuse
          └── no: generate and persist
                 ▼
          execute pending blocks
          max concurrency = 3
                 ▼
          persist every outcome
                 ▼
          failures?
          ├── retryable → failed_recoverable
          ├── terminal  → failed_terminal
          └── none      → assemble from DB
                               ▼
                         persist document
                               ▼
                         required visuals?
                         ├── yes → awaiting_visuals
                         └── no  → ready
```

## Ownership

### Approval request

Owns revision validation, approval persistence, queue transition, and a quick response. It does not own form planning, writers, assembly, or PDF generation.

### Worker

Owns claim, heartbeat, resume, planners/writers, failure classification, stage transitions, and final assembly.

### Repository

Owns atomic transitions, lease metadata, persisted artifacts, structured errors, event history, and document revision.

### Renderer/PDF service

Reads the persisted native document and applies teacher/student projections.

## Canonical state machine

```text
awaiting_teaching_approval
        ↓ approve
queued
        ↓ claim
planning_forms
        ↓ form plan persisted
writing_blocks
        ↓ all required blocks complete
assembling
        ↓ document persisted
awaiting_visuals ───────┐
        ↓ visuals ready │ callbacks
        └───────────────┘
ready
```

Failures:

```text
active stage → failed_recoverable → queued
active stage → failed_terminal
any nonterminal → cancelled
```

`GenerationModel.status` is authoritative. `chunked_state.stage` may remain only as a compatibility mirror written by the same transition method.

## Worker choice

Use a database-leased in-process worker.

Advantages:

- survives browser disconnect;
- reclaims work after restart;
- requires no new service;
- fits the existing database and proof stage.

Do not use FastAPI `BackgroundTasks` as the durability mechanism. Do not add Celery yet.

## Execution identity

```text
section_id:block_id:variant_id
```

Default variant: `everyone`.

## Resume rules

```text
ready             → skip
visual_pending    → skip writer
failed retryable  → retry
failed terminal   → do not retry automatically
missing           → execute
stale started     → retry after lease expiry
```

Planning resumes at stage granularity. Writers resume per block.

## Writer concurrency

Use max-three concurrent LLM calls. Do not share one SQLAlchemy `AsyncSession` across those calls. Writer tasks return immutable outcomes; a coordinator persists safely.

## Assembly invariant

Assembly must reload the form plan and block outcomes from the database, enumerate exact expected keys, reject missing/failed/duplicate/mismatched results, order deterministically, assemble, validate, persist, and reload in a fresh session.

The process-local result list is never authoritative.

## Figure lifecycle

A pending figure keeps its block identity and stable request ID. After assembly the generation is `awaiting_visuals` until required assets are ready. PDF export must refuse final output while required visuals are pending.

## Delivery invariant

One `LectioDocumentV2`, two projections:

```text
teacher edition → answers and teacher-only material visible
student edition → answers and teacher-only material absent
```

## Phase boundary

Weak content is acceptable in Phase 02. Missing resilience is not.

# Xplore Native Phase 02 — Completion and Resilience Pack

**Version:** 1.0  
**Date:** 2026-08-05  
**Repository:** `richiewaweru/lectio-xplore-monorepo`  
**Branch:** `pageobject-integration`  
**Baseline commit:** `00cc3c7eea7c8d3bf5e56b4988f261e07aa247d6`

## Mission

Patch 01 proved that conceptual, factual, and procedural lesson shapes enter the native whole-lesson path and reach the teacher gate. Phase 02 makes the native back half finish reliably:

```text
APPROVE TEACHING
→ durable queued execution
→ form plan
→ resumable block writers
→ DB-first assembly
→ LectioDocumentV2 persistence
→ direct reload
→ teacher PDF
→ student PDF
```

The phase is complete only when one native lesson survives a forced writer failure and backend restart, then completes without regenerating ready blocks. After that, four official lessons must be recorded from a single commit.

## Verification policy

Browser automation is **not required**. Cursor verifies through:

1. API drivers against the local application.
2. Direct database inspection.
3. Structured logs and native event history.
4. Deterministic failure injection.
5. Backend restart and lease-reclaim tests.
6. Fresh-session document reload.
7. Direct PDF endpoint calls.
8. PDF text extraction and teacher/student answer-visibility assertions.
9. Optional screenshots only when reliable.

A browser screenshot is supplementary evidence, not a completion gate.

## Contents

```text
01_ARCHITECTURE/
  PHASE_02_RESOLVED_ARCHITECTURE.md
  STATE_MACHINE_AND_WORKER_DESIGN.md
02_PATCH/
  PATCH_02_NATIVE_COMPLETION_AND_RESILIENCE.md
03_IMPLEMENTATION/
  CURSOR_PHASE_02_EXECUTION_PROMPT.md
  IMPLEMENTATION_SEQUENCE.md
04_VERIFICATION/
  PHASE_02_VERIFICATION_PROTOCOL.md
  FAILURE_INJECTION_MATRIX.md
  PHASE_02_CHECKLIST.md
05_EVIDENCE_TEMPLATES/
  RUN_MANIFEST.template.md
  DB_VERIFICATION.template.json
  BLOCK_EXECUTION_REPORT.template.json
  PDF_ASSERTIONS.template.json
  PHASE_02_REPORT.template.md
06_HANDOFF/
  FINAL_ACCEPTANCE_GATE.md
```

## Scope boundary

Phase 02 changes operation and resilience. It does not tune pedagogy.

Out of scope unless structurally necessary:

- teaching/writer prompt rewrites;
- complete `typical_intents` coverage;
- item-budget or question-quality expansion;
- Builder editing;
- new page-object contracts;
- Celery/Redis/Kafka or another queue;
- historical v1 migration;
- broad UI redesign;
- model-tier experiments.

## Core principles

1. `GenerationModel.status` is canonical.
2. Approval returns promptly and never performs the back half inline.
3. Database records, not process memory, drive resume and assembly.
4. A failed block does not cancel independent siblings.
5. Ready blocks are never regenerated during resume.
6. Required pending figures block final PDF export.
7. Teacher and student editions are projections of one persisted `LectioDocumentV2`.
8. No new generation may fall back to `resume_stage2`.

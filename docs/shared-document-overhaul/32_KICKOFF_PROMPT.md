# Kickoff Prompt

You are starting the Lectio Shared Document Overhaul.

Your source-of-truth implementation pack is the extracted `lectio_shared_document_overhaul/` directory (place it under `docs/shared-document-overhaul/` if working inside the repository). Read `00_START_HERE.md` first, then read the numbered pack in order before changing code.

The target architecture is:

```text
Preparation
  → Enriched Teaching Plan
  → Teacher Approval
  → SharedLessonDocument
  → Learn / Print
```

Teaching Plan owns pedagogy and continuity. SharedLessonDocument owns the exact learner-facing ordinary lesson. Learn and Print own medium-specific realization only. Ordinary content is authored once.

Converge durable generation on one Run/WorkItem model with source-hash verification, idempotent admission, leases/fencing, checkpoints, bounded calls, typed failures, targeted retry, atomic success commit and persisted telemetry.

For all LLM work, reuse the repository's existing `ModelSlot.FAST`, `ModelSlot.STANDARD`, `ModelSlot.PREMIUM` plus its existing AuthoringEngine/structured-provider/model-spec infrastructure. Do not introduce a second model-routing abstraction. Introduce truthful new capability names in that infrastructure as needed, and remove obsolete V2/V3 capability names once zero-called.

This is a clean-cut product architecture migration, not a backwards-compatibility program. Temporary parallel paths exist only for proof. Once a replacement passes its gate, prove zero callers and delete superseded generation logic, prompts, routes, tests, adapters, state handling and database structures that the current product no longer needs.

Before implementation:
1. create/check out the dedicated overhaul branch;
2. record actual current `main` SHA and DB migration head in `30_RUNBOOK.md`;
3. execute Phase 0 baseline verification;
4. compare current repository shape with `01_CURRENT_BASELINE.md`;
5. if there is material drift, report it before changing architecture.

Then execute `29_PHASED_IMPLEMENTATION_PLAN.md` in order.

For every phase:
- implement only the phase responsibility;
- keep contracts typed and closed;
- run contract, integration and failure tests;
- update `30_RUNBOOK.md`;
- commit a coherent checkpoint;
- do not mark PASS before its exit gate.

Never fix a blocker by creating a second architecture, weakening hash/approval guarantees, adding unbounded retries, or allowing Learn/Print to author ordinary content again. Escalate the exact conflict to the orchestrator.

The final repository must contain one obvious current lesson-generation architecture and guards preventing deleted paths from returning.

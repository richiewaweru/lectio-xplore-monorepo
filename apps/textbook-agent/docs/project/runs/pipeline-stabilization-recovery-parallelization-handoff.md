# Pipeline Stabilization + Failed-Section Recovery Handoff

**Runbook**: `docs/project/runs/pipeline-stabilization-recovery-parallelization.md`  
**Status**: validated  
**Scope**: backend pipeline stabilization, partial-rerun recovery, phased section execution, and frontend failed-section visibility

## What Was Fixed

- Pre-assembly section failures are now persisted instead of disappearing silently.
- `content_generator` now gets one bounded schema-repair attempt before a section is marked failed.
- Partial enhance flows now rerun only failed or missing sections while preserving successful sections.
- Diagram handling now has mode-specific timeouts, explicit outcome tracking, and a separate retry budget that avoids repeated timeout waste.
- The per-section pipeline now runs through explicit phases with a parallel-safe middle stage.
- The textbook page now shows failed sections and reacts to `section_failed` stream events in real time.

## Important Design Choices

- Failed sections stop at the node where they broke; they do not flow downstream.
- The repair budget is intentionally bounded to one attempt.
- `interaction_decider` was intentionally kept in the runtime path for compatibility even though composition planning is now added upstream.
- The first speed win here is from targeted reruns and bounded diagram retries, not from aggressive new LLM concurrency.

## Validation

- Backend full suite from `backend/`: `128 passed`
- Frontend full suite: `44 passed`
- Architecture check passed
- Full repo validation passed

Validation note:

- backend validation must run from `backend/` in this workspace
- repo validation still requires `LECTIO_CONTRACTS_DIR=C:\Projects\Textbook agent\backend\contracts`

## Key Files

- `backend/src/pipeline/nodes/content_generator.py`
- `backend/src/pipeline/nodes/composition_planner.py`
- `backend/src/pipeline/nodes/process_section.py`
- `backend/src/pipeline/nodes/section_runner.py`
- `backend/src/pipeline/graph.py`
- `backend/src/textbook_agent/interface/api/routes/generation.py`
- `backend/src/textbook_agent/application/services/generation_report_recorder.py`
- `frontend/src/routes/textbook/[id]/+page.svelte`

## Remaining Context

- `structure.txt` and `textbook_agent.db` are untracked local artifacts and were not included in the code changes.
- This branch is the implementation branch for the coordinated stabilization + recovery push and is ready to push as the current source of truth for this workstream.

## Pickup Path

If follow-up tuning is needed, start with:

1. `backend/src/pipeline/nodes/content_generator.py`
2. `backend/src/pipeline/nodes/diagram_generator.py`
3. `backend/src/pipeline/nodes/process_section.py`
4. `backend/src/textbook_agent/interface/api/routes/generation.py`
5. `frontend/src/routes/textbook/[id]/+page.svelte`

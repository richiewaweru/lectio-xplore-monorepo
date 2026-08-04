# Inline QC + Targeted Retry Stabilization Handoff

**Runbook**: `docs/project/runs/inline-qc-targeted-retry-stabilization.md`  
**Status**: validated  
**Scope**: backend-only stabilization of inline QC, retry routing, retry state, and diagnostics/report emission

## What Was Fixed

- The generation-killing `SectionReportUpdatedEvent` crash is fixed by normalizing assembler reports to `source="assembler"` at the publisher boundary.
- Pending retry state is now consumable per section instead of append-only, so retries can be queued, re-routed, and cleared safely.
- `qc_agent` now runs at the intended per-section scope and no longer scans every assembled section during inline QC.
- `retry_diagram` and `retry_field` now behave like real composites: they rerun assembler + QC after patching content, refresh QC reports, and persist retry-count changes.

## Why This Matters

The immediate exception was only the first symptom. The larger problem was that the March 22 retry rollout had crossed the graph topology over to inline QC without also crossing over the state model and composite execution model. This handoff closes that gap so the retry path is both crash-free and bounded.

## Validation

- Targeted pipeline integration/tests passed
- Generation report recorder tests passed
- Interface tracing/API tests passed
- Architecture check passed
- Full repo validation passed

Validation note:
- Repo-root interface/full validation in this workspace required `LECTIO_CONTRACTS_DIR=C:\Projects\Textbook agent\backend\contracts`

## No Public Contract Changes

- SSE/report payloads stay the same
- `SectionReportUpdatedEvent.source` still exposes only `assembler | qc_agent`
- `report_url` and `section_manifest` behavior are unchanged

## Remaining Context

- This stabilization sits inside a larger existing dirty tree for pipeline speed work.
- Adjacent WIP files remain outside this fix scope and are called out in the runbook so they are not mistaken for part of this handoff.

## Pickup Path

If more retry/QC work is needed, start with:
1. `backend/src/pipeline/nodes/section_runner.py`
2. `backend/src/pipeline/nodes/qc_agent.py`
3. `backend/src/pipeline/graph.py`
4. `backend/src/pipeline/routers/qc_router.py`
5. `backend/tests/pipeline/test_pipeline_integration.py`

# Open Questions and Evidence Spikes

These are not invitations for Cursor to decide silently. They are evidence tasks with explicit default behavior.

## Q1 — Exact persisted document owner

**Need:** identify whether final legacy content lives in a generation state JSON, a generation table field, editable lesson table, or multiple stores.  
**Default:** reuse the canonical final-document store; no new column until proven necessary.  
**Owner:** Run 00.

## Q2 — Backend schema generation tool

**Need:** determine whether existing `tools/update_lectio_contracts.py` already uses a generator suitable for the v2 schema.  
**Default:** extend existing patterns; avoid a second generator stack.  
**Owner:** Run 01.

## Q3 — Application print route

**Need:** confirm the currently maintained builder/generation print route and readiness event.  
**Default:** reuse it; do not create a parallel PDF service.  
**Owner:** Runs 00 and 06.

## Q4 — Section-title rendering in current page package

**Need:** current commit notes indicate `section.title` may be navigation-only.  
**Decision:** change renderer so it is visible exactly once as h2.  
**Owner:** Run 01.

## Q5 — First-slice worked example

A conceptual lesson may not honestly need a worked example.  
**Default:** do not force the object into the golden lesson. Use a separate writer fixture.  
**Owner:** Runs 03–04.

## Q6 — Real-model planner test budget

**Default:** all phase gates use deterministic mocked outputs and fixtures. Real calls require `ALLOW_PAID_LLM_TESTS=1` and an explicit run instruction.  
**Owner:** human-controlled evaluation after Run 03.

## Q7 — Backend semantic validation parity

**Default:** share invalid/valid JSON fixtures between TypeScript and Python. Do not attempt to execute TypeScript validator from Python at runtime.  
**Owner:** Runs 01 and 05.

## Q8 — Variant persistence

**Default:** first slice core only. Preserve current variant metadata but do not create variant-specific block differences until Phase 08.  
**Owner:** Phase 08.

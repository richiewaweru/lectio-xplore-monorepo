# Cursor Run 03 — Native Section Block Planning

## Goal

Produce a complete, validated page-block plan from a real approved lesson while leaving content unwritten.

## Work

1. Install the v2 structural prompt that produces card/anchor/section metadata without components.
2. Install the section-level block planner prompt from this pack.
3. Add strict output models and planner agents using existing `run_llm` infrastructure.
4. Add a feature-flagged v2 branch in the approved-path preparation flow.
5. For v2, do not call `run_component_selector`.
6. Resolve candidates deterministically before every section call.
7. Plan sections sequentially and pass only summaries of earlier section plans.
8. Validate the whole block plan after all sections.
9. Add fixture/mocked planner tests and a dry-run CLI. Default mode must not spend money.
10. Persist the structural/block plan in the existing generation state only if Phase 0 established a safe additive location; otherwise return it from the test harness and record the persistence dependency for Run 05.

## Stop conditions

- v2 requires modifying objective ownership;
- v2 would silently fall back to components;
- candidate matrix is insufficient and would require inventing catalogue policy;
- a paid call is required for the gate.

## Gate

A conceptual first-exposure fixture produces sections whose blocks have contiguous positions, valid closed pairs, specific evidence, and specific briefs. A spy proves the component selector was not called.

## Commit

`feat(planning): plan ordered page objects for xplore lessons`

# Cursor Run 02 — Planning Contracts and Candidate Resolver

## Goal

Add native page-block planning types and deterministic narrowing without changing production generation.

## Work

1. Add generated/canonical literal types where available.
2. Add additive `PlannedBlock` and `SectionBlockPlan` models.
3. Add `SectionPlan.blocks` with a safe default while retaining `components`.
4. Add a document/planning version discriminator so persisted legacy plans parse unchanged.
5. Extend resource-spec schema with page vocabulary and section block bounds. Do not add stance.
6. Migrate only lesson vocabulary required for conceptual first exposure.
7. Add candidate intents to relevant skeleton slots while retaining `allowed_components` for v1.
8. Implement `resolve_block_candidates` returning explicit intent→object candidate matrices.
9. Exclude non-selectable intents, answer-key, and heading from first-slice planning.
10. Add exhaustive tests for migrated section/resource combinations and exact empty-intersection errors.

## Gate

- all legacy plan fixtures parse unchanged;
- first-slice sections have non-empty candidate matrices;
- every pair is catalogue-compatible;
- excluded intents/objects never appear;
- heading never appears;
- no production behavior changed.

## Commit

`feat(planning): add native page block contracts and candidates`

# Phase D — Establish Explicit Single-Path Admission

## Goal
Keep the existing independent realization foundation, but make the user-selected Print or Learn path the normal production request.

## Open these active files first
- `apps/textbook-agent/backend/src/application/unit_lesson/realization_contracts.py`
- `apps/textbook-agent/backend/src/application/unit_lesson/realizations.py`
- `apps/textbook-agent/backend/src/application/unit_lesson/dual_native.py`
- `apps/textbook-agent/backend/src/application/unit_lesson/dispatch.py`
- `apps/textbook-agent/backend/src/curriculum/routes.py`
- `apps/textbook-agent/backend/src/curriculum/models.py`

## Implementation tasks
- Preserve `NativePath`, realization identity, Teaching Plan revision/hash pins, independent retry/status, and separate output IDs.
- Change request contracts/UI defaults so one explicitly selected path is admitted at a time.
- Retire `dual_native.py` if it only exists to generate both paths together; move any genuinely shared helper elsewhere.
- Ensure later generation of the sibling path starts again from the approved Teaching Plan.
- Remove package-contract assumptions that will become invalid when `@lectio/learn` is retired/reduced.

## Expected outputs
- `single-path realization request contract`
- `updated Unit route response/status model`
- `independent Print and Learn realization tests`

## Acceptance gate
Generate Learn only; confirm no Print output is created. Then request Print from the same Teaching Plan; confirm a separate Print realization is created without reading Learn output.

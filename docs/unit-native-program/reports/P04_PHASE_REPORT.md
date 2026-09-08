# Phase report

Phase: P04 — Connect closed native selectors and writer plans
Status: PASS
Starting commit: `b2fac75` (P03 PASS report head) / ending code commit: `0a30c1b` — last implementation/test commit every gate below was run against. This report is committed on top of it and changes no product code.
Dirty files preserved: `.tmp/**`, `apps/textbook-agent/backend/.tmp/*.log`, `apps/textbook-agent/backend/data/` — none committed.

Contract/spec/prompt versions:

| Artefact | Version / note |
|---|---|
| Print native policy | `print/resources/native_policy.py` v1 (offer/deny/budgets/assets) |
| Learn native policy | `learn/resources/native_policy.py` v1 (content + interactions incl. Sequence) |
| Selection snapshots | `PrintSelectionSnapshot` / `LearnSelectionSnapshot` with sealed hash |
| Writer views | `@lectio/page` form-writer-view; `@lectio/learn` learn-writer-view |
| Work orders | `print/generation/work_orders.py`, `learn/generation/work_orders.py` |

Dependencies verified: P03 PASS at `d0f6e16` / report `b2fac75`.

## Changes and purpose

### Print (`print/resources` + `print/generation`)

- Closed per-block form eligibility: package ∩ native policy ∩ intent/action ∩ assets ∩ writer support ∩ approved-item binding ∩ budgets.
- Selection snapshot/hash + attributable validation (`OUT_OF_SET`, `MISSING_BLOCK`, `DUPLICATE_BLOCK`, `ALTERED_TEACHING_IDENTITY`).
- Form planner candidate map delegates to the closed selector; planner payload carries compact learner-action briefs.
- Exact Print work orders and scoped writer requests (selected payload schema only; sibling sentinels never interpolated).

### Learn (`learn/resources` + `learn/generation`)

- Closed content/interaction candidate derivation with optional interaction=`none` and typed `NO_COMPATIBLE_CAPABILITY`.
- `reconstruct-order` alias → `order-items` so Sequence is selectable without vocabulary forks.
- Deterministic closed selection + sealed snapshots; work-order compiler with capability-specific schemas.
- Typed activity authoring: approved-item consumption vs new authoring; incompatible task type raises `ACTION_SOURCE_INCOMPATIBLE` (no silent rewrite).

### Application

- Realization admission policies re-exported from Print/Learn owner modules so policy hash changes invalidate only that path.

## Gate evidence

All commands run from `apps/textbook-agent/backend` with `uv run`. Evidence under `docs/unit-native-program/evidence/mocks/p04/`.

| Gate ID | Test or command | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|
| P04-N01 | `uv run pytest -q tests/print_learn/test_p04_native_selection_gates.py::test_p04_n01_compare_without_response_and_sequence` | Passive compare selects content without interaction; order-items/reconstruct-order can select Sequence | 1 passed, exit 0 | PASS | `n01-compare-sequence.txt` |
| P04-N02 | `...::test_p04_n02_selection_errors_are_attributable` | Out-of-set, missing, duplicate, altered identity fail with attributable codes | 1 passed, exit 0 | PASS | `n02-selection-errors.txt` |
| P04-N03 | `...::test_p04_n03_optional_none_and_required_incompatibility` | Empty optional → none; empty required → NO_COMPATIBLE_CAPABILITY; no silent fallback | 1 passed, exit 0 | PASS | `n03-optional-required.txt` |
| P04-N04 | `...::test_p04_n04_writer_requests_exclude_sibling_schemas` | Writer requests carry only selected schema/facts/refs; sibling sentinels never leak | 1 passed, exit 0 | PASS | `n04-writer-schema-scope.txt` |
| P04-N05 | `...::test_p04_n05_coverage_dependencies_and_assets` | Native plan covers every block; dependencies preserved; missing assets block gated caps | 1 passed, exit 0 | PASS | `n05-coverage-assets.txt` |
| P04-N06 | `...::test_p04_n06_policy_change_shifts_eligibility_without_component_edits` | Policy deny/offer changes eligibility without editing component definitions or selector branches | 1 passed, exit 0 | PASS | `n06-policy-change.txt` |

Supporting: `n01-n06-pytest.txt` (full P04 suite, 7 passed).

## Failure attribution and repairs

- Print N06 fixture initially asserted `aside` under intent `explain`; form-selection cards mark aside intent-unsupported for explain — switched the policy-deny probe to `prose`, which is legally offered.

## Migration and compatibility

- No DB migration. Additive modules only.
- Existing `build_form_candidate_map` remains the Print planner entry and now applies native policy.
- Realization policy bodies moved to path owners; admission hash semantics unchanged aside from richer policy fields.

## Decisions or deviations

- D-018: Incomplete Learn interactions (e.g. Sequence) may be policy-selected when a writer schema exists; generation-ready/Builder repair remains P06 (aligns with D-007).
- D-019: `reconstruct-order` is accepted as an alias of `order-items` at selection time only.

## Remaining risk / blocked access

- P04 does not claim live Print PDF export or Learn publish success (P05/P06).
- LLM form/content selectors still use the closed candidate fence; deterministic selection is the gate authority for eligibility and work-order compile.
- Interaction shells remain `planned`/`incomplete` for end-to-end generation until Builder repair (P06).

## Next phase

P05 (Print production) and P06 (Learn authoring/publish) may proceed in parallel after this PASS.

Next commands:
- P05: read `docs/unit-native-program/pack/phases/P05_PRINT_PRODUCTION.md`
- P06: read `docs/unit-native-program/pack/phases/P06_LEARN_AUTHORING.md`

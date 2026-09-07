# Phase report

Phase: P02 — Implement shared preparation and teaching
Status: PASS
Starting commit: `584db4d` (P01 PASS report head) / ending code commit: `962c362` — last implementation/test commit every gate below was run against. This report is committed on top of it and changes no product code.

Contract/spec/prompt versions:

| Artefact | Version / note |
|---|---|
| Shared teaching models | `curriculum/teaching_plan/` (new) |
| Learner action briefs | `guided` \| `independent` + `source_item_ids` / `dependencies` |
| `@lectio/contracts` teaching view | 1.0.0 (unchanged from P01) |
| Unit preparation | Shared semantic plan; `document_contract_version=1`; no native components |

Dependencies verified: P01 PASS at `5a73e31` / report `584db4d`.

## Changes and purpose

### Shared Unit preparation (`application/unit_lesson`)

Fresh path preparation no longer claims a print-native document contract or selects components:

- Provider packet is a typed allowlist projection (`project_shared_preparation_packet`) with no `allowed_components`, forms, or `document_contract_version`.
- Skeleton slot **roles** stay pedagogical; repeated roles get unique **instance ids** (`apply-1`, `apply-2`).
- Variant materialization creates empty semantic sections — first-allowed-component synthesis removed.
- Chunked state records `shared_preparation=True` and `components_selected=False`; `native_whole_lesson` is not set at prepare time (P03 owns realization identity).

### Teaching ownership (`curriculum/teaching_plan/`)

Instructional teaching models and services moved out of Print ownership:

- Models: `TeachingPlan` (+ optional `learner_action`), drafts, materialization, revision records.
- Compatibility: approved item kind vs learner action — incompatible bindings raise `ACTION_SOURCE_INCOMPATIBLE` rather than rewriting assessment meaning.
- Revisions: `TeachingRevisionStore` keeps approved snapshots readable after edits.
- Consumers: Print and Learn call `accept_approved_teaching_revision` on the **same** stored plan (no fixture substitution).
- Print keeps a re-export shim at `print/generation/whole_lesson/teaching_plan.py` and adapts via `plan_shared_teaching` (single planner, not a duplicate).

### Validation / repository

- Teaching validation checks learner-action / source compatibility.
- `PageDocumentRepository.save_teaching_plan` / `save_teaching_review` record and approve revisions through the curriculum store.

## Gate evidence

All commands run from `apps/textbook-agent/backend` with `uv run`. Evidence under `docs/unit-native-program/evidence/mocks/p02/`.

| Gate ID | Test or command | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|
| P02-S01 | `uv run pytest -q tests/curriculum/test_p02_shared_plan_gates.py::test_p02_s01_shared_prep_no_native_inventory_and_sentinels` (+ related teaching draft/validation) | Real Unit prep → shared plan; no components/forms; sentinel tokens absent from serialized provider request | 21 passed (batch) / 1 passed (gate), exit 0 | PASS | `s01-prep-sentinels.txt` |
| P02-S02 | `...::test_p02_s02_objective_refs_scope_and_code_owned_ids` | Objective drift rejected; card id/objective code-owned; invented MCQ→order binding fails | 1 passed, exit 0 | PASS | `s02-objective-refs.txt` |
| P02-S03 | `...::test_p02_s03_zero_misconceptions_modes_and_repeated_apply_ids` | Zero-misconception previews for conceptual/procedural/factual; repeated apply → unique instance ids | 1 passed, exit 0 | PASS | `s03-modes-repeated-slots.txt` |
| P02-S04 | `...::test_p02_s04_print_and_learn_accept_identical_revision` (+ curriculum façade smoke) | Print and Learn accept identical approved revision without rewriting intents/roles | 2 passed, exit 0 | PASS | `s04-dual-consumer.txt` |
| P02-S05 | `...::test_p02_s05_incompatible_source_fails_without_rewrite` | MCQ cannot bind to `order-items`; open item cannot bind to `select-one` | 1 passed, exit 0 | PASS | `s05-source-compat.txt` |
| P02-S06 | `...::test_p02_s06_edit_creates_revision_old_approved_readable` | Edit → revision 2 pending; revision 1 remains readable by id | 1 passed, exit 0 | PASS | `s06-teaching-revisions.txt` |

Supporting: `s01-s06-pytest.txt` (full P02 + path_bridge + teaching draft suite, 29 passed).

## Failure attribution and repairs

- Path-bridge fakes/assertions updated for shared preparation (`document_contract_version=1`, `PathStructuralPagePlan` semantic sections).
- D6A prepare assertions retargeted to `shared_preparation` (print realization identity deferred to P03).

## Migration and compatibility

- Additive only: teaching revision ledger lives in chunked generation state (`teaching_revisions`).
- Print import paths for `TeachingPlan*` remain valid via shim (same class objects).
- Legacy generations with `native_whole_lesson` remain readable; new prepares do not set that flag.

## Decisions or deviations

- D-012: Teaching models live under `curriculum/teaching_plan/`; Print re-exports and adapts.
- D-013: Shared prep persists `StructuralPlan.document_contract_version=1` with empty components rather than inventing a third contract version; print-native v2 is a realization concern (P03).
- D-014: Single-occurrence slot instance ids keep the bare role (`orient`); only repeated roles use `role-N` suffixes.

## Remaining risk / blocked access

- Full Print/Learn production chains after shared prep still need P03 realization identity to re-attach a native path without smuggling it into shared meaning.
- No live provider teaching run claimed in this phase (deterministic unit/integration only).

## Next phase

P03 — realization identity and dual-path pinning.

Next command: read `docs/unit-native-program/pack/phases/P03_*.md` and `pack/contracts/03_*.md`, confirm P02 gates PASS, then implement additive realization rows that pin the approved teaching revision for Print and Learn.

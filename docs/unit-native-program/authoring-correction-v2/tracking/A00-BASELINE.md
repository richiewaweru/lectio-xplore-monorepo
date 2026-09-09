# A00 Baseline

## Repository Identity

- Branch: `feat/unit-print-learn`
- Baseline HEAD: `998e9f36e75f81899a6405a5d199e2f246bcbf9c`
- A00 scope: documentation plus failing regression tests only. No product fixes were implemented.

## Dirty Work To Preserve

Pre-existing worktree state includes unrelated generated/run artifacts that must not be reverted:

- P05 page image status: `docs/unit-native-program/evidence/mocks/p05/images/p04-page-image-status.json`
- P05 overflow image: `docs/unit-native-program/evidence/mocks/p05/images/overflow-page-1.png`
- Repository `.tmp/` files, including prior contract, frontend, pytest, and P09 evidence captures.
- Backend runtime artifacts under `apps/textbook-agent/backend/.tmp/`.
- Backend local data under `apps/textbook-agent/backend/data/`.
- P09 scripts:
  - `apps/textbook-agent/backend/scripts/run_p09_export_pdfs.py`
  - `apps/textbook-agent/backend/scripts/run_p09_salvage_attempts_a.py`
  - `apps/textbook-agent/backend/scripts/run_p09_v05_failure_recovery.py`

## Command Map

Commands copied from `docs/unit-native-program/COMMAND_MAP.md` for this baseline:

| Owner | Purpose | Command | Cwd | Recorded status |
| --- | --- | --- | --- | --- |
| `@lectio/page` | Package tests | `pnpm page:test` | repo root | PASS (41) |
| `@lectio/page` | Package check | `pnpm page:check` | repo root | PASS |
| `@lectio/learn` | Package tests | `pnpm --dir packages/lectio-learn test` | repo root | PASS (131) |
| `@lectio/learn` | Package check | `pnpm --dir packages/lectio-learn check` | repo root | PASS (0 errors, 2 CSS warnings) |
| Frontend | Typecheck | `pnpm app:check` | repo root | PASS |
| Frontend | Unit tests | `pnpm app:test` | repo root | PASS (347) |
| Frontend | Production build | `pnpm --dir apps/textbook-agent/frontend build` | repo root | PASS |
| Domain guards | Package + backend boundaries | `pnpm program:domain-guards` | repo root | PASS |
| P08 integration | Dual-path gates I01-I06 | `uv run pytest -q tests/print_learn/test_p08_integration_gates.py` | `apps/textbook-agent/backend` | PASS (5) |
| Backend | Alembic heads | `uv run alembic -c alembic.ini heads` | `apps/textbook-agent/backend` | PASS `20260907_0040` |
| Backend | Disposable upgrade | `DATABASE_URL=.../lectio_p00_gate_b04 uv run alembic upgrade head` | backend | PASS |
| Contracts | Sync page contracts | `pnpm contracts:sync` | repo root | available |
| Contracts | Learn export | `pnpm --dir packages/lectio-learn export-contracts` | repo root | available |

Test DB policy from the command map:

- Use disposable Postgres DB `lectio_p00_gate_b04` for migration gates.
- Do not reset production `textbook_agent` DB.
- SQLite alembic upgrade is not a valid substitute.

## Production Call Graphs

### Print

1. Unit approval state is loaded by `print.generation.whole_lesson.executor.execute_after_teaching_approval`.
2. If no reusable valid form plan exists, the executor calls `print.generation.native_production.build_closed_print_production_plan`.
3. Closed Print production builds candidates with `print.generation.catalogue_projections.build_form_candidate_map`, validates legality with `print.generation.whole_lesson.validation.validate_form_plan`, then compiles work orders with `print.generation.work_orders.compile_print_work_orders`.
4. The executor writes selected form blocks via `print.generation.whole_lesson.executor.write_form_blocks`.
5. Each block reaches `print.generation.whole_lesson.executor._write_one_block`, builds a `WriterContext`, and calls `print.rendering.page_objects.registry.dispatch_writer_async`.
6. `dispatch_writer_async` either calls the provider-backed `_write_validated_llm` path or deterministic stub writers. On current baseline, table and figure provider failures fall back to deterministic stubs.
7. Successful block outcomes are persisted by `PageDocumentRepository`; final assembly uses `assemble_from_db`, `assemble_section`, and `assemble_document_v2`.

### Learn

1. Approved shared teaching enters `learn.generation.native_execution.produce_learn_from_approved_teaching`.
2. This calls `learn.generation.native_production.build_closed_learn_production`.
3. Closed Learn production hashes teaching, builds a sealed selection with `learn.generation.native_selection.build_learn_selection_snapshot`, derives candidates through `learn.resources.selection.build_learn_candidate_map`, and compiles work orders with `learn.generation.work_orders.compile_learn_work_orders`.
4. Learn assembly calls `learn.generation.ordered_assemble.assemble_ordered_learn_document`.
5. Interaction work orders are authored by `learn.generation.interaction_writer.write_interaction_from_work_order`, which builds a scoped request and dispatches to deterministic interaction writers.
6. Content blocks are currently assembled by `_content_block_from_decision`, which copies teaching block briefs into body-like fields instead of invoking generation-enabled content authoring.
7. The Learn document is remapped for Builder host compatibility by `host_interaction_blocks_for_builder` and persisted as a completed `GenerationModel` plus editable lesson draft.

## Requirement To File Mapping

Detailed mapping is in `tracking/A00-REQUIREMENT_MAP.md`. Summary:

- Print provider failure handling: `print/rendering/page_objects/registry.py`, `print/generation/whole_lesson/executor.py`, tested by `test_a00_print_table_fallback.py`.
- Learn interaction answer correctness for the core 8 interactions: `learn/generation/interaction_writer.py`, tested by `test_a00_arbitrary_answers.py`, with broader requirement coverage in `A00-REQUIREMENT_MAP.md`.
- Learn generation-enabled content: `learn/generation/ordered_assemble.py`, `learn/generation/native_production.py`, tested by `test_a00_brief_as_content.py`.
- Learn native selection policy: `learn/generation/native_selection.py`, `learn/resources/selection.py`, tested by `test_a00_first_content_selection.py` and `test_a00_fallback_budget.py`.

## A00 Regression Commands

Run from `apps/textbook-agent/backend`:

```bash
uv run pytest -q tests/authoring_correction/test_a00_arbitrary_answers.py
uv run pytest -q tests/authoring_correction/test_a00_brief_as_content.py
uv run pytest -q tests/authoring_correction/test_a00_print_table_fallback.py
uv run pytest -q tests/authoring_correction/test_a00_first_content_selection.py
uv run pytest -q tests/authoring_correction/test_a00_fallback_budget.py
uv run pytest -q tests/authoring_correction
```

Failure evidence for A00 is stored under `docs/unit-native-program/authoring-correction-v2/evidence/a00/`.

## Observed A00 Failure Evidence

All A00 regression commands were run from `apps/textbook-agent/backend` on branch `feat/unit-print-learn` at baseline HEAD `998e9f36e75f81899a6405a5d199e2f246bcbf9c`.

| Command | Exit | Evidence |
| --- | ---: | --- |
| `uv run pytest -q tests/authoring_correction/test_a00_arbitrary_answers.py` | 1 | `docs/unit-native-program/authoring-correction-v2/evidence/a00/tests_authoring_correction_test_a00_arbitrary_answers.py.txt` |
| `uv run pytest -q tests/authoring_correction/test_a00_brief_as_content.py` | 1 | `docs/unit-native-program/authoring-correction-v2/evidence/a00/tests_authoring_correction_test_a00_brief_as_content.py.txt` |
| `uv run pytest -q tests/authoring_correction/test_a00_print_table_fallback.py` | 1 | `docs/unit-native-program/authoring-correction-v2/evidence/a00/tests_authoring_correction_test_a00_print_table_fallback.py.txt` |
| `uv run pytest -q tests/authoring_correction/test_a00_first_content_selection.py` | 1 | `docs/unit-native-program/authoring-correction-v2/evidence/a00/tests_authoring_correction_test_a00_first_content_selection.py.txt` |
| `uv run pytest -q tests/authoring_correction/test_a00_fallback_budget.py` | 1 | `docs/unit-native-program/authoring-correction-v2/evidence/a00/tests_authoring_correction_test_a00_fallback_budget.py.txt` |
| `uv run pytest -q tests/authoring_correction` | 1 | `docs/unit-native-program/authoring-correction-v2/evidence/a00/tests_authoring_correction.txt` |

Failure reasons:

- `test_a00_numeric_uses_independent_answer_not_first_number`: current numeric writer returns `5.0` from the first prompt number instead of expected `50`.
- `test_a00_fill_blank_uses_supplied_answer_not_last_word`: current fill-blank writer returns `___.` from the prompt text instead of expected `chlorophyll`.
- `test_a00_choice_rejects_invalid_correct_key_instead_of_first_option`: current choice writer accepts invalid key `z` and does not raise; it falls back to a declared option.
- `test_a00_ordered_assemble_does_not_copy_brief_as_content_body`: current Learn assembly copies `Explain evaporation with an everyday example.` as content body.
- `test_a00_table_llm_failure_surfaces_typed_failure_not_lit_leaf_stub`: current Print table dispatch swallows provider timeout and returns deterministic stub content.
- `test_a00_explain_content_selection_is_semantic_not_first_candidate`: current Learn selector chooses `callout-block`, the first content candidate, instead of expected `explanation-block`.
- `test_a00_fallback_candidate_stays_excluded_when_budget_exhausted`: current Learn fallback restores `explanation-block` even with remaining budget `0`.

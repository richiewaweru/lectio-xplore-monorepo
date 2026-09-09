# R00 Baseline

## Repository identity

- Branch: `feat/unit-print-learn`
- Baseline HEAD: `db157f00731602c35ec1ec1e71fd5cc5d21e655b`
- R00 scope: documentation, v2 gate reopen notes, and failing regression tests only. No product fixes.

## Dirty work to preserve

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

## Command map

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
| P08 integration | Dual-path gates I01–I06 | `uv run pytest -q tests/print_learn/test_p08_integration_gates.py` | `apps/textbook-agent/backend` | PASS (5) |
| Backend | Alembic heads | `uv run alembic -c alembic.ini heads` | `apps/textbook-agent/backend` | PASS `20260907_0040` |
| Backend | Disposable upgrade | `DATABASE_URL=…/lectio_p00_gate_b04 uv run alembic upgrade head` | backend | PASS |
| Contracts | Sync page contracts | `pnpm contracts:sync` | repo root | available |
| Contracts | Learn export | `pnpm --dir packages/lectio-learn export-contracts` | repo root | available |

Test DB policy from the command map:

- Use disposable Postgres DB `lectio_p00_gate_b04` for migration gates.
- Do not reset production `textbook_agent` DB.
- SQLite alembic upgrade is not a valid substitute.

## Production call graphs (summary)

Detailed function paths are in `tracking/R00-CALLER_MAP.md`.

### Print

1. Shared preparation state is loaded and both consumers accept the identical revision via `accept_approved_teaching_for_both` / `accept_approved_teaching_revision`.
2. Print resume enters `print.generation.whole_lesson.executor.execute_after_teaching_approval`.
3. Closed selection compiles via `print.generation.native_production.build_closed_print_production_plan` → `build_print_selection_snapshot` → `select_print_deterministically` → `compile_print_work_orders`.
4. Blocks are written by `write_form_blocks` → `_write_one_block` → `print.rendering.page_objects.registry.dispatch_writer_async` → `print.generation.authoring_adapter.run_print_authoring` (provider path).
5. Assembly reloads from DB via `assemble_from_db` → `assemble_section` / `assemble_document_v2`; persistence through `PageDocumentRepository`.

### Learn

1. Shared preparation enters `learn.generation.native_execution.produce_learn_from_approved_teaching`.
2. Closed production runs `learn.generation.native_production.build_closed_learn_production_async`.
3. Selection seals via `learn.generation.native_selection.build_learn_selection_snapshot` → `select_learn_deterministically` (keyword ranking, no model selector hook).
4. Work orders compile with `learn.generation.work_orders.compile_learn_work_orders`.
5. Authoring runs `learn.generation.authoring_adapter.author_learn_work_orders` → `run_learn_authoring` / `interaction_contract_from_authoring_result` through `infra.authoring.engine.AuthoringEngine.execute`.
6. Assembly uses `learn.generation.ordered_assemble.assemble_ordered_learn_document`.
7. Persistence writes `GenerationModel`, `EditableLessonModel`, and realization linkage via `admit_realization`.

## R00 regression commands

Run from `apps/textbook-agent/backend`:

```powershell
uv run pytest -q tests/remaining_fixes/test_r00_incomplete_activity.py
uv run pytest -q tests/remaining_fixes/test_r00_approved_source_leak.py
uv run pytest -q tests/remaining_fixes/test_r00_empty_teaching_context.py
uv run pytest -q tests/remaining_fixes/test_r00_keyword_selection.py
uv run pytest -q tests/remaining_fixes/
```

Evidence captured under `docs/unit-native-program/remaining-fixes-v3/evidence/r00/`.

## Reviewed defects reproduced (no fixes)

| Defect | R spec | Regression test | Intended failure reason |
| --- | --- | --- | --- |
| Brief becomes student prompt; generic feedback | R1 | `test_r00_incomplete_activity.py` | Provider-authored question/feedback not preserved; brief substituted |
| Positional approved pool binding | R2 | `test_r00_approved_source_leak.py` | No-ref order converts `approved_items[0]`; q1 sentinel visible for explicit q2 |
| Hardcoded empty teaching context | R3 | `test_r00_empty_teaching_context.py` | `author_learn_work_orders` receives `allowed_facts=[]` despite prep facts |
| Keyword ranking instead of model selector | R4 | `test_r00_keyword_selection.py` | Ambiguous shortlist picks `ranked[0]`; selector provider never invoked |

## v2 gate reopen

A02, A04, A05, and A06 offline PASS claims are reopened in `docs/unit-native-program/authoring-correction-v2/tracking/` because R00 regressions expose defects those gates did not independently prove on current HEAD. Historical evidence paths are preserved and labelled historical.

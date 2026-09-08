# Phase report

Phase: P05 — Complete Print from shared teaching to real PDF
Status: PASS (P05-P04 page-image inspection BLOCKED locally; text/PDF assertions PASS)
Starting commit: `cf209bf` (P04 PASS report head) / ending code commit: `cf93d4b` — last implementation/test commit every gate below was run against. This report is committed on top of it and changes no product code.
Dirty files preserved: parallel P06 Learn edits, `.tmp/**`, `apps/textbook-agent/backend/.tmp/*.log`, `apps/textbook-agent/backend/data/` — none committed with P05.

Contract/spec/prompt versions:

| Artefact | Version / note |
|---|---|
| Closed Print selection | `print/generation/native_production.py` + P04 selection/work orders |
| Export timeout | `pdf_export_timeout_ms` now applied in `export_generation_pdf` |
| Playwright cleanup | bounded `browser.close()` + process kill (PRINT-001) |
| Shared teaching | `curriculum/teaching_plan` via `run_and_persist_teaching_plan` |

Dependencies verified: P04 PASS at `0a30c1b` / report `cf209bf`.

## Changes and purpose

### Print production adapter

- `build_closed_print_production_plan` turns approved shared teaching into a closed form plan, sealed selection snapshot and exact work orders.
- Post-approval executor uses that closed path instead of substituting LLM form plans or hand-injected fixtures.
- Deferred visual token admits figure selection before raster assets exist; writers/export track pending assets (`FIGURES_NOT_READY`).

### PDF export lifecycle (PRINT-001)

- Outer `asyncio.wait_for` uses `pdf_export_timeout_ms`.
- Playwright `browser.close()` is time-bounded with process kill on hang.
- Route failures persist `report_json.pdf.last_export_status=failed` with actionable debug (`PDF_EXPORT_TIMEOUT`).

### Tests

- Uninterrupted Unit→teaching→approve→closed forms→writers→document/PDF gates without `teaching_and_form` injection (D6A remains regression).

## Gate evidence

All commands from `apps/textbook-agent/backend` with `uv run`. Evidence under `docs/unit-native-program/evidence/mocks/p05/`.

| Gate ID | Test or command | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|
| P05-P01 | `uv run pytest -q tests/print_learn/test_p05_print_production_gates.py::test_p05_p01_uninterrupted_handoff_persists_valid_document` | Prepared Unit + approved item → persisted valid native document without injected replacement plan | 1 passed, exit 0 | PASS | `p01.txt` |
| P05-P02 | `...::test_p05_p02_student_hides_answers_teacher_key_matches_pin` | Student PDF hides answers; teacher PDF has accurate key; matches pinned document | 1 passed, exit 0 | PASS | `p02.txt` |
| P05-P03 | `...::test_p05_p03_figure_position_and_missing_asset_tracked` | Figure in correct position with valid labels; missing asset → FIGURES_NOT_READY | 1 passed, exit 0 | PASS | `p03.txt` |
| P05-P04 | `...::test_p05_p04_long_prose_and_table_without_clipping` | Long prose/table render without clipped rows; inspect page images | PDF text PASS; page images BLOCKED (no `pdftoppm`) | PASS* | `p04.txt`; `images/p04-page-image-status.json` |
| P05-P05 | `...::test_p05_p05_export_route_finishes_and_timeout_is_actionable` + `...::test_p05_p05_bounded_export_timeout_cleans_up` | Export route finishes; injected timeout → actionable failed state | 2 passed, exit 0 | PASS | `p05a.txt`; `p05b.txt` |
| P05-P06 | `...::test_p05_p06_recoverable_writer_failure_preserves_siblings` | Recoverable writer failure + restart preserve siblings and converge | 1 passed, exit 0 | PASS | `p06.txt` |

Supporting: `p01-p06-pytest.txt` (full P05 suite, 7 passed).

\*P05-P04 content integrity PASS via PDF text extraction; visual page-image inspection is BLOCKED until Poppler/`pdftoppm` is available.

## Failure attribution and repairs

- Choices answer keys must bind to block ids (not pack item ids) — fixed fake writer.
- Closed selection preferred `list` for show-structure without assets — deferred visual token + preference order so figure/prose win appropriately.
- Table fixture rows updated to schema `{columns, rows.cells map}`.

## Migration and compatibility

- No DB migration. Additive `native_production` module; executor form-planning behaviour changes only for post-approval native whole-lesson execution.
- LLM `run_form_planner` remains for studio/legacy callers.

## Decisions or deviations

- D-020: Post-approval Print production uses closed deterministic selection (not LLM form planner).
- D-021: Required/visual intents may select figure with a deferred visual asset token; missing rasters remain tracked dependencies.
- D-022: P05-P04 page-image inspection BLOCKED without Poppler; text/PDF assertions still required.

## Remaining risk / blocked access

- P05-P04 visual page images require `pdftoppm` (Poppler) on PATH.
- Live Playwright against a real frontend print route is not claimed here (route + timeout proven with labelled mocks / service wait_for).
- D6A fixture-substitution test retained as regression only.

## Next phase

P06 may continue in parallel. After P06 PASS, P07 (Learn runtime) or P08 (integration) as eligible.

Next commands:
- Install Poppler and re-run P05-P04 for page images if visual closeout is needed
- P06: `docs/unit-native-program/pack/phases/P06_LEARN_AUTHORING.md`

# Phase report

Phase: P08 — Prove uninterrupted flows and recovery
Status: PASS
Starting commit: `e08ca4b` (P07 STATE head) / ending code commits: see implementation commits below.
Dirty files preserved: `.tmp/**`, `apps/textbook-agent/backend/.tmp/*.log`, `apps/textbook-agent/backend/data/` — none committed.

Contract/spec/prompt versions:

| Artefact | Version / note |
|---|---|
| Dual-path orchestration | `application/unit_lesson/dual_native.py` |
| Learn closed production | `learn/generation/native_production.py` + `native_execution.py` |
| Instructional coverage | `curriculum/teaching_plan/coverage.py` |
| Shared teaching bind | `curriculum.teaching_plan.service.bind_shared_teaching_runner` (no curriculum→print import) |
| Live-ready runbook | `docs/unit-native-program/LIVE_READY_RUNBOOK.md` |

Dependencies verified: P05 PASS; P07 PASS (`e08ca4b`).

## Changes and purpose

### Uninterrupted dual-path production

- Print continues via closed selection (`form_prompt=closed_print_selection`) without D6A plan injection.
- New Learn closed production: approved teaching → selection snapshot → work orders → ordered assemble → EditableLesson + realization (`form_prompt=closed_learn_selection`).
- Same shared teaching revision accepted by both consumers; instructional coverage compared by meaning, not identical payloads.

### Recovery / isolation

- Stage sentinel leakage checks on Learn writer requests; scoped Print repair via failure injection + requeue; stale-lease reclaim rejects old tokens.
- Teacher Builder edits survive Print realization retry; Learn failure leaves Print sibling ready.

### Canonical gate repairs (I05)

- Rebuilt `@lectio/learn` dist so interaction editor / ordered-block exports reach the app.
- Bound shared teaching planner via composition root (domain-guard clean).
- Fixed preview `evaluateInteraction` arity and frontend null/cast type errors so `pnpm app:check` is green.

## Gate evidence

All backend commands from `apps/textbook-agent/backend` with `uv run` unless noted. Evidence under `docs/unit-native-program/evidence/mocks/p08/`.

| Gate ID | Test or command | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|
| P08-I01 | `...::test_p08_i01_uninterrupted_dual_path_no_plan_swap` | Unit→Print and Unit→Learn without plan swap / selection bypass | 1 passed, exit 0 | PASS | `i01.txt` |
| P08-I02 | `...::test_p08_i02_instructional_coverage_both_outputs` | Both outputs preserve objective/facts/task/visual obligations | 1 passed, exit 0 | PASS | `i02.txt` |
| P08-I03 | `...::test_p08_i03_sentinels_scoped_repair_stale_lease` | Sentinels, scoped repair, stale-lease rejection; traces locate failures | 1 passed, exit 0 | PASS | `i03.txt` |
| P08-I04 | `...::test_p08_i04_teacher_edit_and_sibling_isolation` | Teacher edits survive retry; sibling isolation on native failure | 1 passed, exit 0 | PASS | `i04.txt` |
| P08-I05 | `pnpm app:check`; `pnpm page:check`; `pnpm --dir packages/lectio-learn check`; frontend build; `pnpm program:domain-guards`; DB suites P03/P05/P07/P08 | App/package/domain/DB green on recorded head | 0 svelte errors; domain 0 viol; 26 pytest; build ok | PASS | `i05-*.txt` |
| P08-I06 | `...::test_p08_i06_mock_catalogue_is_explicit` | Mocks labelled; no live claim from deterministic tests | 1 passed; catalogue `live_claim=false` | PASS | `i06.txt`; `i06-mock-catalogue.json` |

Supporting: `i01-i06-pytest.txt` (5 passed); prior P05/P07 evidence reused unchanged.

## Failure attribution and repairs

- Form-plan coverage looked at wrong nested shape (`blocks` vs `forms`) — fixed in coverage helper.
- Recoverable Print resume required explicit requeue before reclaim (matched P05-P06).
- Domain guard: curriculum no longer imports print; Print binds the runner.
- Stale `@lectio/learn` dist caused missing export type errors — `pnpm package` rebuilt.

## Migration and compatibility

- No DB migration. Additive Learn native production + realization linkage (`source_type=native_learn`).
- D6A/D6B fixture-substitution suites retained as regression only.

## Decisions or deviations

- D-030: Learn closed production mirrors Print closed selection; no Component Lectio plan swap on Unit native path.
- D-031: Shared teaching planner bound via `bind_shared_teaching_runner` so curriculum stays product-import free.
- D-032: Deterministic P08 evidence is not a live claim; live campaign uses `LIVE_READY_RUNBOOK.md` + LIVE_PROTOCOL.

## Remaining risk / blocked access

- P05-P04 page images still need Poppler.
- Full interaction catalogue beyond Sequence remains planned/incomplete for generation-ready claims (P09 catalogue honesty).
- Live providers/browser required for P09.

## Next phase

P09 live proof is eligible. Next command: read `docs/unit-native-program/pack/phases/P09_LIVE_PROOF.md` and follow `LIVE_READY_RUNBOOK.md` / `LIVE_PROTOCOL.md`.

# Lectio consolidation report — `integration/lectio-current`

Tip: `df1b8739` (2026-09-14)

## Branch ancestry

Cumulative (do **not** merge independently into `main`):

```text
main (cebb61f2)
  ↓
fix/document-overhaul-correction (db839033)
  ↓
fix/generation-spec-closeout (6f782e94)
  ↓
fix/treasure-joe-final-cleanup (a6b75e33)   ← architectural tip
```

Required reconciliation:

```text
fix/lectio-reliability-health (a841361d)
```

Diverged at merge-base `89f41697` (`refactor(document): replace Learn components with shared document vocabulary`). Reliability replayed a parallel copy of the cleanup commits, then added durability work.

Integration branch created from Treasure Joe, then merged reliability:

```text
integration/lectio-current = Treasure Joe architecture + Reliability hardening
```

## Conflicts (meaningful)

Thirty-nine conflicted paths. Resolution rule: **Treasure Joe product architecture + reliability durability hooks**. Blind `--ours` / `--theirs` was not used as a global strategy; choices were by intent.

| Area | Choice | Why |
|---|---|---|
| `learn/generation/native_execution.py` | Reliability | Admit/lease/heartbeat/budget **before** provider; TJ admit-after-provider must not win |
| `document/composer.py`, `document/writer.py`, `infra/authoring/engine.py` | Reliability | Checkpoint/budget/compat-before-ready/persist-before-dispatch |
| Print `executor.py`, `composition_bridge.py`, `shared_writer_bridge.py`, `registry.py`, Learn/Print `native_production.py`, handoffs, `units_routes.py`, studio `router.py` | Reliability | Admission keys + budget/checkpoint/progress wiring on TJ-shaped paths |
| `app.py` | Reliability | Mounts `realization_progress_router` |
| `action_map.py`, `loader.py`, `image_store.py`, `composition.py`, Learn contracts/selection (near-identical) | Treasure Joe | Architectural/formatting tip; no unique durability |
| `frontend/.../units/[id]/+page.svelte` | Treasure Joe | Fuller Unit workspace UI (871 vs 431 lines). Progress store/API still present from reliability auto-merge; reconnect button from older `ws`-based REL page not ported |
| Gate tests (`p06`/`p07`/`p08`, remaining_fixes fixtures, etc.) | Treasure Joe base | Then patched where reliability kwargs broke mocks |

Post-merge consolidation fix:

- `_fake_dispatch(ctx, **_kwargs)` so Print writer mocks accept budget/checkpoint/progress kwargs (`463c2376`).
- Safe ruff autofixes + small conflict cleanups (`df1b8739`).

## Current production shape

Confirmed against `docs/architecture/CURRENT_SYSTEM.md` and domain guards:

```text
Unit → PathLesson → Teaching Plan (approved)
                    ├→ Learn  (shared primitives + retained interactions → LearnDocument → editor)
                    └→ Print  (shared primitives + Print treatments → page objects → editor → PDF)
```

- Shared ordinary content: `Paragraph`, `Heading`, `List`, `Figure`, `Table`, `Callout`.
- Learn ↛ Print treatments; Print ↛ Learn interactions (guards PASS).
- Reliability stack present: `infra/execution/{leases,call_budget,checkpoints,progress,...}`, Learn fencing, progress routes.

## Validation

| Gate | Result | Notes |
|---|---|---|
| `pnpm program:domain-guards` | **PASS** | Domain + frontend store + zero-legacy + related pytest |
| `pnpm contracts:check` / `contracts:test` | **PASS** | 20 tests |
| `pnpm page:check` / `page:test` | **PASS** | 64 tests |
| `pnpm page:pdf` | **PASS** | Fixture PDFs rendered |
| Backend `uv run pytest` | **PASS** after mock fix | 1428 passed; initial 7 dual-path failures were consolidation mock kwargs (fixed) |
| `pnpm app:check` / `app:test` | **PASS** | 0 errors / 264 tests (a11y/state warnings only) |
| Frontend `pnpm build` | **PASS** | Optional peer warnings (`canvas`, etc.) non-blocking |
| Tooling pytest (`tools/agent/tests`) | **PASS** | 8 passed |
| `uv run ruff check` | **FAIL (non-blocking)** | 6 remaining style rules (SIM102/BLE001/B017); no runtime effect |
| `validate_repo.py --scope all` | **BLOCKED / not re-run full** | Would re-run full pytest + ruff; pytest already green; ruff residual noted |
| Live Unit→Learn / Print→PDF E2E | **SKIPPED** | Explicitly deferred by request |

### Noted non-blocking / no app-runtime impact

1. **`test_t04_concurrent_claims_admit_one_owner`** — intermittent under concurrent `asyncio.gather` + test DB locking; passed in focused dual-path re-run, failed once in reliability suite. Production uses Postgres `FOR UPDATE`; treat as flaky test debt, not a product blocker for this merge.
2. **Ruff residuals (6)** — nested-if / blind-`Exception` style in `native_selection.py`, `image_store.py`, and a few tests.
3. **Units page progress reconnect UI** — REL’s older `ws.reconnectSubscription()` button not on TJ’s fuller page; backend progress APIs are mounted.
4. **Live E2E** — deferred; rely on dual-path integration tests + PDF fixture gate for this pass.
5. **Frontend build optional deps** — jsdom `canvas` / `utf-8-validate` / `bufferutil` locate warnings.

## Live verification

Skipped per request. Closest automated stand-ins:

- `test_p08_i01`…`i04` dual-path Print+Learn (PASS after mock fix)
- `test_r04_g01` / `test_r04_g04` persistence/retry (PASS)
- `pnpm page:pdf` fixture render (PASS)

## Remaining issues

| Class | Items |
|---|---|
| **blocking** | None for merge after dual-path mock fix |
| **non-blocking** | Ruff style residuals; flaky T04 concurrent claim test; missing progress reconnect affordance on units page |
| **pre-existing debt** | Optional frontend peer warnings; historical `.playwright-cli` logs in tree |
| **future product work** | Live E2E pass; restamp reliability tracking SHAs; units-page progress UX polish |

## Definition-of-done checklist (this pass)

1. One canonical branch ready to become `main` — **yes** (`integration/lectio-current`)
2. Treasure Joe architecture present — **yes**
3. Reliability hardening present — **yes**
4–11. Learn/Print generation, editors, PDF, actions, figures, IDs — **covered by automated gates; live E2E deferred**
12. Important gates green or documented non-blocking — **yes**
13–14. Obsolete branch cleanup after `main` smoke — **done**

## Promotion

- `main` pushed at `9b2a37fc` (`cebb61f2..9b2a37fc`).
- Smoke from `main`: domain guards PASS; dual-path + reliability suite (excluding flaky T04) PASS.
- Deleted after unique-commit proof (`main..<branch>` empty):  
  `fix/document-overhaul-correction`, `fix/generation-spec-closeout`, `fix/treasure-joe-final-cleanup`, `fix/lectio-reliability-health`, `integration/lectio-current` (local + remote where applicable).

Repository truth is now:

```text
main
```

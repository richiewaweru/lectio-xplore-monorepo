# Phase report

Phase: P03 — Separate native output identity and state
Status: PASS
Starting commit: `f92e51a` (P02 PASS report head) / ending code commit: `d0f6e16` — last implementation/test commit every gate below was run against. This report is committed on top of it and changes no product code.
Dirty files preserved: `.tmp/**`, `apps/textbook-agent/backend/.tmp/*.log`, `apps/textbook-agent/backend/data/` — none committed.

Contract/spec/prompt versions:

| Artefact | Version / note |
|---|---|
| Realization identity | `application/unit_lesson/realization_contracts.py` + `NativeRealizationModel` |
| Native paths | `print` \| `learn` persisted at admission |
| Policy / package fingerprints | print policy v1 + `@lectio/page` 1.1.0; learn policy v1 + `@lectio/learn` 1.0.0 |
| Alembic | `20260908_0041` → head after `20260907_0040` |

Dependencies verified: P02 PASS at `962c362` / report `f92e51a`.

## Changes and purpose

### Realization identity (`application/unit_lesson`)

- Explicit requested outputs via `POST .../realizations` with fields from contracts/03.
- Independent rows per path; idempotency on `(path_lesson_id, path, teaching_plan_revision, variant_id, native_policy_hash, package_contract_hash)`.
- Path pinned at admission; retries bump `realization_revision` / `output_id` only for that row.
- Shared teaching revision change → `stale` without clearing snapshot `output_id`; policy hash change invalidates only that path.
- Ambiguous legacy backfill → `read_only` + `variant_id=legacy-ambiguous` (no guessed Print/Learn).

### Persistence (`infra`)

- Additive `native_realizations` table + unique identity constraint.
- Migration backfills from `path_lessons.pack_id` using unambiguous markers only.
- `pack_id` retained as a legacy link, not the dual-path discriminator.

### Status / open / retry + Unit UI

- Lesson status returns realization list plus Print/Learn open hrefs.
- Units generation status/open/retry accept `path` / `realization_id` query params.
- Unit page shows both Open Print and Open Learn when present; read-only legacy is surfaced.

## Gate evidence

All commands run from `apps/textbook-agent/backend` with `uv run`. Evidence under `docs/unit-native-program/evidence/mocks/p03/`.

| Gate ID | Test or command | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|
| P03-R01 | `uv run pytest -q tests/application/test_p03_realization_gates.py::test_p03_r01_dual_outputs_idempotent` | One lesson creates Print+Learn; duplicate request reuses rows | 1 passed, exit 0 | PASS | `r01-dual-idempotent.txt` |
| P03-R02 | `...::test_p03_r02_print_retry_leaves_learn_and_plan` | Print retry leaves Learn output/plan; inverse proven | 1 passed, exit 0 | PASS | `r02-print-retry-isolated.txt` |
| P03-R03 | `...::test_p03_r03_persisted_path_survives_default_change` | Changed default pipeline cannot flip persisted path | 1 passed, exit 0 | PASS | `r03-path-pin.txt` |
| P03-R04 | `...::test_p03_r04_shared_revision_marks_stale_keeps_snapshots` | Shared revision → stale; old snapshots intact; path regen independent | 1 passed, exit 0 | PASS | `r04-stale-snapshots.txt` |
| P03-R05 | `...::test_p03_r05_legacy_backfill_ambiguous_read_only` | Unambiguous backfill; ambiguous → read-only; regenerate allowed | 1 passed, exit 0 | PASS | `r05-legacy-readonly.txt` |
| P03-R06 | `...::test_p03_r06_concurrent_uniqueness_and_status_routing` | Concurrent create unique; status/open identify correct artifact | 1 passed, exit 0 | PASS | `r06-concurrent-routing.txt` |

Supporting: `r01-r06-pytest.txt` (full P03 suite, 7 passed).

## Failure attribution and repairs

- Concurrent admit initially rolled back the whole session; switched to `begin_nested` savepoints so IntegrityError resolves to the surviving row.
- Admission no longer invents a non-existent `output_id`; status falls back to preparation generation until the native artifact exists.

## Migration and compatibility

- Additive table only; downgrade drops `native_realizations`.
- Legacy `path_lessons.pack_id` remains the shared preparation link.
- Ambiguous historical generations are readable as `read_only` and must be regenerated with an explicit path.

## Decisions or deviations

- D-015: Realization identity lives in `native_realizations` (not chunked-state-only) so uniqueness is transaction-safe.
- D-016: Ambiguous legacy uses `variant_id=legacy-ambiguous` so it does not block later explicit Print/Learn admission under `everyone`.
- D-017: Shared preparation generation may temporarily back status reads when a realization is queued without an output artifact yet; `realization_id`/`path` remain authoritative.

## Remaining risk / blocked access

- Native selection/writing (P04+) still attach writers to these identities; this phase does not claim live Print PDF or Learn publish success.
- Alembic upgrade against a disposable Postgres DB was not re-run here; schema is covered by SQLAlchemy `create_all` + migration script review (same pattern as P02 unit gates).

## Next phase

P04 — native planning / selection against pinned realizations.

Next command: read `docs/unit-native-program/pack/phases/P04_*.md` and `pack/contracts/03_*.md` native planning section; implement Print/Learn selectors that consume the admitted realization identity and approved teaching revision.

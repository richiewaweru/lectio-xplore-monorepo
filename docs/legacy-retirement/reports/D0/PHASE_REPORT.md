# D0 Report — Legacy Dependency Census

Status: PASS

## Starting state
- branch: `refactor/domain-ownership`
- SHA: `2aa7bdee9f3a36483c99920b3a2ea243153ccb3f`
- dirty_state: untracked `.tmp/`, backend `data/`, frontend/backend `*.log` only; no product-code edits in D0
- prior programs: `docs/refactor-program` (R0–R8 PASS), `docs/cleanup-program` (C0–C5 PASS)
- `docs/legacy-retirement/` did not exist (no prior D-report / LEGACY_STATE / manifest)
- program packet unzipped to `.tmp/xplore-legacy-retirement/xplore_legacy_retirement_d0_d5_program/`
- permanent docs reread: NORTH_STAR, CANONICAL_OWNERSHIP, LEGACY_RETIREMENT_RULES, DEFERRED_PRODUCT_FIXES, FINAL_ACCEPTANCE_D5
- Unit path treated as sole supported creation path

## Subsystems handled
Census only (no moves). Live `app.py` drift vs C0 noted: mounts `curriculum.routes` and `infra.telemetry` directly; `application.unit_lesson` exists but re-exports `planning.bridge`.

Classifications written to `docs/legacy-retirement/LEGACY_DEPENDENCY_MANIFEST.json`:

| Subsystem | Classification | retirement_order |
|---|---|---|
| app_composition_root | KEEP_CANONICAL | 0 |
| application | KEEP_CANONICAL (unit_lesson still re-export) | 0 |
| curriculum | KEEP_CANONICAL | 0 |
| print | KEEP_CANONICAL | 0 |
| learn | KEEP_CANONICAL | 0 |
| infra | KEEP_CANONICAL | 0 |
| packages_lectio_page | KEEP_CANONICAL | 0 |
| packages_lectio_learn | KEEP_CANONICAL | 0 |
| planning | MIGRATE_AND_DELETE | 1 |
| generation | MIGRATE_AND_DELETE | 2 |
| builder | MIGRATE_AND_DELETE | 3 |
| telemetry_shim_package | MIGRATE_AND_DELETE | 4 |
| core_residual | MIGRATE_AND_DELETE | 5 |
| resource_specs | MIGRATE_AND_DELETE | 6 |
| contracts_hub | MIGRATE_AND_DELETE | 7 |
| media | MIGRATE_AND_DELETE | 8 |
| v3_blueprint / v3_execution / v3_review | MIGRATE_AND_DELETE | 9 |
| learning_shim_package | DELETE_NOW | 10 |
| curriculum_compatibility_legacy_units | MIGRATE_AND_DELETE | 11 |
| learn_packs_api | MIGRATE_AND_DELETE | 11 |
| frontend_non_unit_surfaces | MIGRATE_AND_DELETE | 11 |
| legacy_database_objects | DATA_RETIREMENT_REQUIRED | 12 |

No `UNKNOWN_BLOCKER` entries: every listed subsystem classified from live imports/mounts/FE callers/startup/DB/config/tests/docs.

### Key live evidence
- Unit prepare: `curriculum.routes` → `application.unit_lesson` → `planning.bridge.prepare_path_lesson` → `generation.path_preparation`
- Unit Print hop still via `/api/v1/v3/.../approve` + `print.generation.whole_lesson` worker
- Unit Learn hop via `generation.units_routes` approve → `learn.generation.component_lectio` → `builder.routes` / LearnRelease
- Unsupported but still live: `/studio*`, `/packs*`, `/units/legacy`, `/builder/new`, `/api/v1/blocks/generate`, `/api/v1/skeletons*`, `/api/v1/legacy-units`, `/api/v1/packs`
- `learning/` package: zero production `src` importers (tests still import shim — not a keep reason)
- `telemetry/` package: 3 production importers remain
- ORM: `Base.metadata` loads **42** tables (models split across `core.database.models` + learn runtime model modules); Alembic head `20260906_0039`

## Consumers migrated
None (D0 inventory only).

## Routes/jobs/telemetry/config retired
None (D0 inventory only). Recorded for later:
- D3 candidates: skeletons, blocks/generate, legacy-units, packs, studio UX beyond Unit Print hops
- Startup still initializes resource specs, skeleton catalog, v3 stale-generation sweep, native worker, telemetry monitor

## DB impact
Classified only — no schema changes. `legacy_database_objects` marked `DATA_RETIREMENT_REQUIRED` for D4 (packs/shadow/trace candidates; preserve migration history).

## Deletions
None executed.

## Compatibility shims retained
All existing shims retained (planning/*, generation pdf/page_objects/v3_studio/units_dispatch, builder.service, learning/*, telemetry/*, core→infra shims, contracts/lectio*, resource_specs candidates/*, learn top-level shims). Removal conditions captured in manifest blockers + retirement_order.

## Tests
| Command / check | Result |
|---|---|
| `pnpm program:domain-guards` | PASS (package + backend 0 violations; 6 pytest passed) |
| ORM metadata load (`core.database.models.Base`) | PASS 42 tables |
| Alembic heads (read-only) | PASS `20260906_0039 (head)` |
| Focused Unit-path pytest (builder + learn releases/runtime + component_lectio lifecycle) | PASS 31 |
| `@lectio/learn` quiz evaluate failure | Deferred product (not D0 FAIL; not re-run as gate) |
| Live Unit Print/Learn browser E2E | Not a D0 gate (C5 residual) |

## Residual risks
- `application.unit_lesson` is not yet real ownership (D1)
- Unit Print still coupled to v3_studio router + v3_* stacks
- FE Unit page deep-links into `/studio` for Print review — must migrate before deleting studio
- Broad `core.*` import surface (78+ modules)
- `learning/` DELETE_NOW still listed in `pyproject.toml` packages=
- Deferred product fixes unchanged (`docs/legacy-retirement/permanent/DEFERRED_PRODUCT_FIXES.md`)

## Ending state
- artifacts: `docs/legacy-retirement/LEGACY_DEPENDENCY_MANIFEST.json`, this report, permanent docs seeded
- product code changed: NO
- safe for next phase: YES
- STOP before D1

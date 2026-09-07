# D1 Report — Canonical Unit Ownership

Status: PASS

## Starting state
- branch: `refactor/domain-ownership`
- SHA: `2aa7bdee9f3a36483c99920b3a2ea243153ccb3f`
- dirty_state: D0 docs uncommitted; `.tmp/` / logs / `data/` untracked
- previous: D0 PASS; `application.unit_lesson` was a re-export of `planning.bridge`

## Subsystems handled
Moved Unit orchestration implementation into `application/unit_lesson/`:

| Module | Role |
|---|---|
| `contracts.py` | `PathPreparationBlocked`, planner/selector type aliases |
| `status.py` | reuse / stale / empty-visual-handoff admission |
| `prepare.py` | `prepare_path_lesson` + structural helpers (from `planning.bridge`) |
| `dispatch.py` | `initialise_path_generation` + `enforce_path_owned_card_objective` (from `generation.path_preparation`) |
| `__init__.py` | exports from **local** modules (no re-export of planning/generation bodies) |

Temporary shims (implementation no longer lives here):
- `planning/bridge.py` → re-exports `application.unit_lesson`
- `generation/path_preparation.py` → re-exports `application.unit_lesson.dispatch`

Also rewired `core.capabilities.require_xplore_v2` to depend on `infra.auth.middleware.get_current_user` / `infra.config.settings` so Unit HTTP tests override the same auth callable the router uses (fixes 401 from dual `core.auth.middleware` ghost binding).

## Consumers migrated
- `curriculum.routes` already imported `application.unit_lesson` (unchanged; now hits real ownership)
- `tests/planning/test_path_bridge.py` → `application.unit_lesson` / `.prepare`
- `tests/planning/test_path_routes.py` → `curriculum.*` + `infra.auth` / `infra.dependencies` for overrides
- `print.http.v3_studio` continues via `generation.path_preparation` shim for `enforce_path_owned_card_objective`

## Routes/jobs/telemetry/config retired
None (D1 ownership only).

## DB impact
None.

## Deletions
None. `planning/` and `generation/` trees retained (shims + remaining live modules for D2+).

## Compatibility shims retained
- `planning.bridge` (temporary)
- `generation.path_preparation` (temporary)
- All prior D0 shims unchanged

## Tests
| Command / check | Result |
|---|---|
| `pnpm program:domain-guards` | PASS |
| ORM metadata | PASS 42 tables |
| Alembic heads | PASS `20260906_0039` |
| Focused Unit-path pytest (path_bridge, path_routes, builder, learn releases/runtime, component_lectio lifecycle) | PASS 61 |

## Residual risks
- `planning.agents` / `v3_blueprint` / `generation.pipeline_dispatch` still imported from application (D2)
- `planning/` / `generation/` still on disk for later evacuation/deletion
- Dual `core.auth.middleware` ghost module remains a broader shim risk outside capabilities

## Ending state
- `application/unit_lesson` owns prepare/dispatch/status/contracts implementation
- safe for next phase: YES
- STOP was required by phase prompt; sequential plan continues to D2 after this PASS

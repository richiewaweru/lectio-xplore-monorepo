# R3 PHASE REPORT — Curriculum + Platform Extraction

Status: PASS

## Starting state
- branch: `refactor/domain-ownership`
- dirty state: R0–R2 Print/Learn domains present

## Move plan executed
| Source | Destination | Ownership | Notes |
|---|---|---|---|
| `telemetry/` | `infra/telemetry/` | PLATFORM | Target-arch name `platform/` → package `infra/` (stdlib clash) |
| `core/auth` | `infra/auth` | PLATFORM | |
| `core/llm` | `infra/llm` | PLATFORM | |
| `core/storage` | `infra/storage` | PLATFORM | |
| `core/middleware` | `infra/middleware` | PLATFORM | |
| `core/health` | `infra/health` | PLATFORM | |
| `core/config.py` (+ logging/errors/rate_limit/events/version/dependencies) | `infra/` | PLATFORM | |
| `core/database/session.py` + `migrations/` | `infra/database/` | PLATFORM | `models.py` left in `core/database` (seam; imports learn runtime models) |
| `planning/{service,routes,models,schedule,outcomes,shapes,linkage,approved_items,compatibility}.py` | `curriculum/` | CURRICULUM | |
| `alembic.ini` script_location | `src/infra/database/migrations` | PLATFORM | |

**Naming decision:** Target architecture folder `platform/` is implemented as import package `infra/` because Python’s stdlib module `platform` shadows a same-named local package. Documented in `infra/__init__.py` and REFACTOR_STATE.

Left in place (ambiguous / seam):
- `core/database/models.py`, entities/ports/repositories/routes/prompts/value_objects, `capabilities.py`, `pdf_export_runtime.py`
- Mixed planning: agents, bridge, page_*, projections, prompts, validation, …
- `media/` (providers vs print topology)

## Compatibility shims
| Shim | Why needed | Removal condition |
|---|---|---|
| `core/auth|llm|storage|middleware|health` | forward to `infra.*` | R7 |
| `core/config|logging|errors|…` | forward to `infra.*` (config exports `_ENV_FILE`) | R7 |
| `core/database/session.py` + migrations package | forward to `infra.database` | R7 |
| `core/database/migrations/versions` junction → infra versions | tools/tests that still resolve old path | Remove after call-site migration; prefer infra path |
| `planning/{curriculum files}.py` | forward to `curriculum.*` | R7 |
| `telemetry/` | forward to `infra.telemetry` | R7 |

## Behavior changes
Expected: NONE.
Observed: NONE.

## Tests
| Command | Result |
|---|---|
| Infra/curriculum smoke + product-import scan | PASS 0 product imports |
| Alembic ScriptDirectory head load | PASS `20260906_0039` |
| `uv run pytest` lifecycle + builder + learn_releases + page_object_writers + page_block_planner | PASS 36 |

## Import/dependency checks
- `infra/` and `curriculum/` do not import print/learn product domains
- Models remain under `core/database` to avoid platform→learn registration edge
- Dependency direction preserved via composition + shims

## Deferred findings
- Package name `infra` vs diagram `platform` — keep mapping documented; do not rename to `platform` without an importlib strategy that beats stdlib.

## Ending state
- safe for next phase: YES

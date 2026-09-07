# R2 PHASE REPORT — Backend Learn Ownership

Status: PASS

## Starting state
- branch: `refactor/domain-ownership`
- SHA: `a5e68a2` (working tree with R0–R1)
- dirty state: Print under `src/print`; historical Print shims

## Move plan executed
| Source | Destination | Ownership | Notes |
|---|---|---|---|
| `learning/*.py` | `learn/*.py` | LEARN | Whole former learning package |
| `generation/component_lectio/` | `learn/generation/component_lectio/` | LEARN | Live Component Lectio pipeline |
| `generation/units_dispatch.py` | `learn/generation/units_dispatch.py` | LEARN | Units→component_lectio admit |
| `builder/service.py` | `learn/authoring/builder/service.py` | LEARN | Builder persistence service |
| `resource_specs/component_candidates.py` | `learn/resources/component_candidates.py` | LEARN | Learn resource candidates |
| `app.py` imports | `learn.release_routes` etc. | PLATFORM | Composition root wiring |
| `core/database/models.py` | import `learn.runtime_models` | PLATFORM | Avoid dual learning path |

Left in place (mixed / seam):
- `builder/routes.py` — Learn CRUD + Print PDF export/preflight (Learn→Print edge). Kept as composition/HTTP surface so `src/learn/**` has **zero** Print imports.
- `generation/units_routes.py` — still under generation; uses Learn via shims
- `v3_blueprint` planning used by component_lectio (R3/R4)

## Compatibility shims
| Shim | Why needed | Removal condition |
|---|---|---|
| `learning/*.py` | forward to `learn.*` | Call sites migrated; R7 |
| `generation/component_lectio/__init__.py` | forward to `learn.generation.component_lectio` | R7 |
| `generation/units_dispatch.py` | forward to `learn.generation.units_dispatch` | R7 |
| `builder/service.py` | forward to `learn.authoring.builder.service` | R7 |
| `resource_specs/component_candidates.py` | forward to `learn.resources.component_candidates` | R7 |

## Behavior changes
Expected: NONE.
Observed: NONE. HTTP prefixes unchanged (`/api/v1/builder`, learn release/runtime routes).

## Tests
| Command | Result |
|---|---|
| Learn shim smoke + Learn→Print scan under `src/learn` | PASS 0 violations |
| `uv run pytest` component_lectio_lifecycle + builder_lessons + learn_releases + learn_runtime | PASS 31 |
| `uv run pytest` page_object_writers + page_block_planner + pdf_export_service | PASS 13 |
| `pnpm --filter @lectio/page test` | PASS 41 |
| `python tools/xplore-program/check_domain_boundaries.py` | PASS |

## Import/dependency checks
- Learn-owned modules discoverable under `src/learn/`
- No Learn→Print imports inside `src/learn/**`
- Residual Learn→Print edge remains only in historical `builder/routes.py` (documented seam for composition extraction)

## Deferred findings
- Extract Builder PDF/preflight routes from `builder/routes.py` into composition-root wiring (not under learn/ or print/) in a later cleanup so the historical builder package can shrink.

## Ending state
- dirty state: R0–R2 tree
- safe for next phase: YES

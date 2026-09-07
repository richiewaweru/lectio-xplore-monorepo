# R1 PHASE REPORT — Backend Print Ownership

Status: PASS

## Starting state
- branch: `refactor/domain-ownership`
- SHA: `a5e68a2e79d370ddc34691099deb5e086eb75319`
- dirty state: R0 docs present; product tree clean of prior moves

## Move plan executed
| Source | Destination | Ownership | Notes |
|---|---|---|---|
| `planning/whole_lesson/` | `print/generation/whole_lesson/` | PRINT | git mv + internal import rewrite |
| `generation/page_objects/` | `print/rendering/page_objects/` | PRINT | git mv + internal import rewrite |
| `generation/pdf_export/` | `print/rendering/pdf/` | PRINT | git mv + internal import rewrite |
| `resource_specs/candidates.py` | `print/resources/candidates.py` | PRINT | git mv; loader/schema remain in resource_specs |
| (new) | `print/__init__.py` + subpackage markers | PRINT | empty package scaffolding |
| `pyproject.toml` hatch packages | add `src/print` | PLATFORM | packaging only |

Left in place (not clearly movable without seam work):
- Print HTTP still hosted by `generation/v3_studio/router.py`
- `planning/page_blocks.py`, `page_projections.py`, `catalogue_projections.py`
- `core/pdf_export_runtime.py`
- `contracts/lectio_page.py`
- Print-adjacent `media/` topology/QC

## Compatibility shims
| Shim | Why needed | Removal condition |
|---|---|---|
| `planning/whole_lesson/__init__.py` | sys.modules forward to `print.generation.whole_lesson` | All call sites use print path; R7 |
| `generation/page_objects/__init__.py` | forward to `print.rendering.page_objects` | R7 |
| `generation/pdf_export/__init__.py` | forward to `print.rendering.pdf` | R7 |
| `resource_specs/candidates.py` | re-export from `print.resources.candidates` | R7 |

## Behavior changes
Expected: NONE.
Observed: NONE.

## Tests
| Command | Result |
|---|---|
| Print import smoke (shim + new paths) | PASS |
| Print→Learn import scan under `src/print` | PASS 0 violations |
| `python tools/xplore-program/check_domain_boundaries.py` | PASS |
| `uv run pytest` page_object_writers + page_block_planner + pdf_export_service + page_candidates | PASS 19 |
| `uv run pytest` component_lectio_lifecycle + builder_lessons + learn_releases | PASS 26 |
| `pnpm --filter @lectio/page test` | PASS 41 |

## Import/dependency checks
- Moved modules resolve under `src/print/...`
- Old import paths still work via temporary shims
- No Print→Learn imports in the new print tree
- Learn→Print edge via `builder/routes.py` → `generation.pdf_export` (shim) still present (expected until R2/R7)

## Deferred findings
- None new. `v3_studio` still hosts Print routes (R0 seam).

## Ending state
- SHA: `a5e68a2` (uncommitted R0+R1 tree)
- dirty state: Print moves + shims + docs
- safe for next phase: YES

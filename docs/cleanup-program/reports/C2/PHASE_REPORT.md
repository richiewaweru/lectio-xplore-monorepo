# C2 REPORT — Complete Domain Separation

Status: PASS

## Starting state
- branch: `refactor/domain-ownership`
- SHA: `25db4a70a6a28e72f189a5d67a9711bab44440c9`
- dirty state: after C1 PASS

## Work performed
- Extracted Builder PDF export + print-preflight into `application/builder_print/routes.py`; mounted from `app.py`; removed Print/PDF imports and those routes from `builder/routes.py` (kept `print-document` GET)
- Moved `generation/v3_studio/` → `print/http/v3_studio/`; left `generation/v3_studio` as shim; `generation/routes.py` and `app.py` import print.http path
- Grouped Learn: `publishing/`, `analytics/`, `runtime/`, plus empty `distribution/` + `evidence/` placeholders; shims at old top-level names
- Updated domain-guard shim list for `generation/v3_studio`

## Moves
| Source | Destination | Reason |
|---|---|---|
| `builder/routes` PDF export/preflight | `application/builder_print/routes.py` | Remove Learn→Print import |
| `generation/v3_studio/*` | `print/http/v3_studio/*` | Print owns studio HTTP |
| `learn/release_routes.py` | `learn/publishing/release_routes.py` | Learn packaging |
| `learn/insight_service.py` | `learn/analytics/insight_service.py` | Learn packaging |
| `learn/runtime_*.py`, `class_service.py` | `learn/runtime/` | Learn packaging |

## Splits / intentional duplication
| Original | New owners | Why |
|---|---|---|
| Builder PDF helpers | application (orchestrates) + print.rendering.pdf | Separation without Print→Learn |

## Deletions
| Path | Classification | Evidence | Coupled tests/docs removed |
|---|---|---|---|
| (none broad) | — | originals replaced by shims where moved | tests patched for PDF mocks |

## Compatibility shims
| Shim | Why retained | Removal condition |
|---|---|---|
| `generation/v3_studio` | external call sites | C3 after migrate |
| `learn/release_routes.py` etc. | external call sites | C3 after migrate |
| planning/generation/core shims | still used | C3 |

## Tests
| Command / flow | Result |
|---|---|
| `create_app()` | PASS |
| `pnpm program:domain-guards` | PASS |
| pytest builder + learn releases + runtime | PASS |

## Deferred findings
- Full body of `planning.bridge` still outside `application/unit_lesson`
- Non-Unit v3 studio UX still mounted (C3 candidate after confirming Unit hops)
- DEAD `canonical_routes.py` / `retirement.py` not deleted yet (C3)

## Ending state
- safe for next phase: YES

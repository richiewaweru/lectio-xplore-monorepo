# C1 REPORT — Canonical Unit-Path Wiring

Status: PASS

## Starting state
- branch: `refactor/domain-ownership`
- SHA: `25db4a70a6a28e72f189a5d67a9711bab44440c9`
- dirty state: prior domain-refactor tree + C0 docs

## Work performed
- Fixed `generation/path_preparation.py:initialise_path_generation` to accept `native_whole_lesson` / `path_plan_raw` and persist them into chunked state (`native_whole_lesson`, `page_document_v2`, `context.native_whole_lesson`, `path_plan_raw`)
- Added thin `application/unit_lesson/` re-exporting `prepare_path_lesson` / `PathPreparationBlocked`
- Rewired `curriculum.routes` to import `application.unit_lesson` as canonical prepare entry
- Rewired `app.py` composition-root imports to `curriculum.*`, `infra.*`, `print.*` (kept mounting same routers including v3; `core.routes.*` remain for auth/profile/prompts/shares/capabilities)
- Restored frontend URL / `$lib` / API prefixes to disk reality (`/studio`, `/builder`, `$lib/learn/authoring/builder`, `$lib/print/components/studio`, `/api/v1/builder`, `/api/v1/auth`, `/settings`)
- Fixed mangled `$lib/builder` leftovers from URL substring replace; fixed ProfileSummary import path

## Moves
| Source | Destination | Reason |
|---|---|---|
| (canonical name) `planning.bridge.prepare_path_lesson` | `application.unit_lesson` re-export | Unit orchestration seam |
| `app.py` shim imports | curriculum/infra/print | Current module names as entrypoints |

## Splits / intentional duplication
| Original | New owners | Why |
|---|---|---|
| (none) | — | Deferred to C2 |

## Deletions
| Path | Classification | Evidence | Coupled tests/docs removed |
|---|---|---|---|
| (none) | — | C1 does not delete | — |

## Compatibility shims
| Shim | Why retained | Removal condition |
|---|---|---|
| `planning.bridge` implementation | Still holds prepare logic | C2 may relocate body under application |
| `planning.*` / `generation.*` / `learning.*` / `telemetry` / `core.*` packages | Call sites remain | C2 migrate + C3 delete |
| Mounted v3_studio / skeletons / packs / legacy-units | API stability | C2 extract Print hops; C3 unmount/delete |

## Tests
| Command / flow | Result |
|---|---|
| `uv run` `create_app()` | PASS 22 routes |
| admission signature + `application.unit_lesson` import | PASS |
| `pnpm program:domain-guards` | PASS |
| pytest builder + learn releases + component_lectio | PASS 26 |
| vitest routing + errors + workspace-shell-styles | PASS 13 |

## Deferred findings
- Builder PDF still in `builder.routes` (C2)
- Print HTTP still in `generation/v3_studio` (C2)
- DEAD leaves `canonical_routes.py` / `retirement.py` not deleted (C3)
- Deferred product fixes unchanged

## Ending state
- SHA: `25db4a70a6a28e72f189a5d67a9711bab44440c9` (uncommitted C1 changes)
- dirty state: C1 wiring + frontend path restore on prior dirty tree
- safe for next phase: YES

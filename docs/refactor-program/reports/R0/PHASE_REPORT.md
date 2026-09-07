# R0 PHASE REPORT — Inventory + Ownership Manifest

Status: PASS

## Starting state
- branch: `refactor/domain-ownership`
- SHA: `a5e68a2e79d370ddc34691099deb5e086eb75319`
- dirty state: untracked evidence/logs/`.tmp` only; seeded `docs/refactor-program/` (not product code)

## Move plan executed
| Source | Destination | Ownership | Notes |
|---|---|---|---|
| (none) | (none) | — | R0 is inventory only; no product-code moves |

Proposed next-phase mechanical candidates (from manifest; not executed):

| Source | Destination | Ownership | Notes |
|---|---|---|---|
| `planning/whole_lesson/` | `print/generation/` | PRINT | R1 |
| `generation/page_objects/` | `print/rendering/page_objects/` | PRINT | R1 |
| `generation/pdf_export/` | `print/rendering/pdf/` | PRINT | R1 |
| `generation/component_lectio/` | `learn/generation/` | LEARN | R2 |
| `builder/` | `learn/authoring/builder/` | LEARN | R2 |
| `learning/` | `learn/` | LEARN | R2 |
| `packages/lectio-learn/` | `packages/lectio-learn/` | LEARN | R6 folder rename |

## Compatibility shims
| Shim | Why needed | Removal condition |
|---|---|---|
| (none) | — | — |

## Behavior changes
Expected: NONE.
Observed: NONE (no product code moved).

## Tests
| Command | Result |
|---|---|
| `python tools/xplore-program/check_domain_boundaries.py` | PASS (0 violations) |
| `pnpm --filter @lectio/page test` | PASS 41/41 |
| `pnpm --filter @lectio/page check` | PASS 0 errors |
| `uv run pytest tests/generation/test_page_object_writers.py tests/planning/test_page_block_planner.py tests/generation/test_pdf_export_service.py -q` (cwd backend) | PASS 13 |
| `uv run pytest tests/generation/test_component_lectio_lifecycle.py tests/routes/test_builder_lessons.py tests/routes/test_learn_releases.py tests/routes/test_learn_runtime.py -q` | PASS 31 |
| `pnpm --dir packages/lectio-learn test` | DOCUMENTED FAIL: 130 passed, 1 failed (`src/test/lectio.test.ts` quiz evaluate / “Not quite!”). Pre-existing at baseline (no R0 code moves). Recorded in DEFERRED_FINDINGS. |
| `pnpm exec vitest run src/lib/api/capabilities.test.ts` + `src/lib/settings/flags.test.ts` (frontend) | PASS |
| Full `src/lib/builder` vitest suite | HUNG in this environment (no output after several minutes); recorded as environment baseline risk. Focused non-svelte frontend tests green. |

## Import/dependency checks

Documented in `docs/refactor-program/OWNERSHIP_MANIFEST.json` (51 items).

Key facts:
- **Print → Learn:** none found.
- **Learn → Print:** `builder/routes.py` imports `generation.pdf_export` (PDF export from Builder). Must extract/invert before hard Print/Learn package isolation.
- Hotspots: `v3_studio`↔`v3_blueprint`↔`v3_execution`; `whole_lesson`↔`page_objects`; `core.database.models`↔`learning.runtime_models`.
- `generation/v3_studio` still hosts live Print HTTP endpoints → classify `NEEDS_SEAM_EXTRACTION` until Print routes extracted (then REMOVE_LATER).
- Ambiguous modules marked `NEEDS_SEAM_EXTRACTION` rather than forced: `planning/`, `generation/` umbrella, `contracts/`, `resource_specs/`, `media/`, `v3_*`, `models.py`, frontend `api/`/`types/`/`components/`/`stores/`.

## Deferred findings
- Known packet deferred fixes unchanged (`permanent/KNOWN_DEFERRED_FIXES.md`).
- New baseline finding: `@lectio/learn` quiz immediate-evaluate test failure in `packages/lectio-learn/src/test/lectio.test.ts` — see `docs/refactor-program/DEFERRED_FINDINGS.md`.
- Frontend full Builder vitest hang under parallel/tee runs — environment risk for later FE phases.

## Ending state
- SHA: `a5e68a2e79d370ddc34691099deb5e086eb75319` (docs-only changes uncommitted)
- dirty state: seeded refactor-program docs + untracked evidence/logs
- safe for next phase: YES

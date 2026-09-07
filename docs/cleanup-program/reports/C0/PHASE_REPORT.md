# C0 REPORT — Reachability Audit

Status: PASS

## Starting state
- branch: `refactor/domain-ownership`
- SHA: `25db4a70a6a28e72f189a5d67a9711bab44440c9`
- dirty state: large uncommitted domain-refactor tree (R1–R8 leftovers) plus residual frontend path rewrite; prior program at `docs/refactor-program/` (R8 PASS)

## Work performed
- Unzipped cleanup program to `.tmp/xplore-canonicalization/xplore_canonicalization_cleanup_program/`
- Seeded `docs/cleanup-program/` with `permanent/`, templates, `CLEANUP_STATE.md`, and this report
- Enumerated FastAPI mounts from `apps/textbook-agent/backend/src/app.py` + nested `generation/routes.py`
- Enumerated lifespan workers, SvelteKit `+page.svelte` routes, package exports, production scripts
- Traced Unit→Print and Unit→Learn call graphs from live symbols
- Classified meaningful backend/frontend/package/docs areas into `REACHABILITY_MANIFEST.json`
- Confirmed DEAD leaves only where all seven deletion criteria hold
- Recorded structural residuals (frontend rewrite mismatch; Unit→Print admission drift; Builder PDF edge; v3_studio hosts Print HTTP)
- Ran light regressions only (no product-code changes)

## Supported graphs (evidence)

### Unit → Learn
1. `curriculum.routes:post_path_lesson_prepare` — `POST /api/v1/units/.../lessons/{id}:prepare` (mounted via `planning.routes` shim)
2. `planning.bridge:prepare_path_lesson`
3. `generation.path_preparation:initialise_path_generation` (`control.pipeline=component_lectio`)
4. `generation.units_routes:approve_units_generation` — `POST .../generation:approve`
5. `learn.generation.units_dispatch:dispatch_units_generation` (via `generation.units_dispatch` shim)
6. `learn.generation.component_lectio.launcher:launch_component_lectio`
7. `learn.generation.component_lectio.service:run_component_lectio_execution`
8. `learn.authoring.builder.service` + `builder.routes` (`/api/v1/builder`)
9. `learn.release_routes:publish_learn_release`
10. `learn.runtime_routes` / analytics

### Unit → Print
1. Same prepare entry as Learn (`curriculum.routes` → `planning.bridge` → `path_preparation`)
2. Print realization still via **v3_studio**: `POST /api/v1/v3/chunked/{id}/approve`
3. `print.generation.whole_lesson.service` → native worker → `executor` → `print.rendering.page_objects`
4. PDF: `v3_studio` export → `print.rendering.pdf.service:export_v3_studio_pdf`

**Reachability break (recorded, not fixed in C0):** `prepare_path_lesson` passes `native_whole_lesson=` and `path_plan_raw=` into `initialise_path_generation`, but that function does not accept those kwargs. Native approve also expects `native_whole_lesson` in chunked state. C1 must repair this admission seam.

## Moves
| Source | Destination | Reason |
|---|---|---|
| (none) | (none) | C0 is inventory only |

## Splits / intentional duplication
| Original | New owners | Why |
|---|---|---|
| (none executed) | — | Candidates recorded in manifest: `builder/routes.py` PDF edges; `generation/` umbrella; `planning/` mix; frontend `lib/api`+`types`+`components`; `core/database/models.py` |

## Deletions
| Path | Classification | Evidence | Coupled tests/docs removed |
|---|---|---|---|
| (none executed) | — | DEAD_CONFIRMED leaves for C3: `generation/canonical_routes.py`, `generation/retirement.py` (zero mounts, zero importers) | — |

## Compatibility shims
| Shim | Why retained | Removal condition |
|---|---|---|
| `planning.routes` → `curriculum.routes` | `app.py` still mounts planning name | Migrate app import; then delete shim |
| `planning.compatibility` → `curriculum.compatibility` | legacy-units mount | Product decision + migrate; then delete |
| `planning.whole_lesson.*` → `print.generation.whole_lesson` | lifespan worker + call sites | Migrate call sites |
| `generation.units_dispatch` → `learn.generation.units_dispatch` | units approve path | Migrate |
| `generation.pdf_export` / `page_objects` → print.* | Builder PDF + writers | Migrate / extract composition |
| `builder.service` → `learn.authoring.builder.service` | routes import shim | Migrate |
| `learning/*` → `learn.*` | historical imports | Migrate call sites |
| `telemetry` → `infra.telemetry` | `app.py` import | Migrate |
| `core.*` infra shims | broad historical surface | Migrate to `infra.*` |

## Mounted but non-Unit surfaces (deletion-eligible after C1 unmount / product decision)
- Full v3 studio UX at `/api/v1/v3/*` (beyond Print approve/PDF hops)
- `/api/v1/skeletons*`, `/api/v1/blocks/generate`
- `/api/v1/legacy-units`, frontend `/units/legacy`
- `/api/v1/packs*` (pack listing; Learn product path is Builder→LearnRelease)
- Frontend `/studio*` as standalone lesson-creation entry (Unit is canonical)

## Frontend structural residual
Disk reality: `/studio`, `/builder`, `$lib/learn/authoring/builder`, `$lib/print/components/studio`, API `/api/v1/builder`.

Broken rewrite still present in many files:
- `/print/studio` (~107 matches)
- `/learn/shared/authoring/builder` (~171 matches)
- `$lib/learn/shared/authoring` (~136 matches)
- `$lib/components/print/studio` (~24 matches; real path is `$lib/print/components/studio`)
- `/api/v1/learn/shared/authoring/builder` (~9 matches; backend prefix `/api/v1/builder`)

**Not the target architecture.** C1 restores strings to match disk/backend.

## Tests
| Command / flow | Result |
|---|---|
| `pnpm program:domain-guards` | PASS (package + backend 0 violations; 6 pytest passed) |
| ORM metadata load (`core.database.models.Base`) | PASS 42 tables |
| Full Builder vitest / Unit E2E | NOT RUN (C0 inventory; reuse R0 hang + deferred notes) |
| `@lectio/learn` quiz evaluate failure | DEFERRED (pre-existing; not C0 FAIL) |

## Deferred findings
- Product fixes from `permanent/DEFERRED_PRODUCT_FIXES.md` unchanged
- Unit→Print prepare/admission kwargs drift (C1)
- Frontend path rewrite mismatch (C1)
- Builder PDF Learn→Print edge (C1/C2 composition extract)
- v3_studio still hosts Print HTTP (extract then C3 delete)
- `@lectio/learn` quiz test + Builder vitest hang (from prior R0/R8 deferred)

## C1 wiring list (explicit)
1. Fix prepare→`initialise_path_generation` admission (kwargs / native flag) or introduce `application/unit_lesson/`
2. Restore frontend URLs/imports/API prefixes to disk reality
3. Rewire `app.py` toward curriculum/print/learn/infra as canonical imports
4. Do not broadly delete legacy yet; keep API behavior stable
5. Stop treating v3 studio UX as canonical lesson creation

## Ending state
- SHA: `25db4a70a6a28e72f189a5d67a9711bab44440c9` (docs-only C0 artifacts uncommitted)
- dirty state: prior refactor dirty tree + new `docs/cleanup-program/` + `.tmp/xplore-canonicalization/`
- safe for next phase: YES
- product code changed: NO

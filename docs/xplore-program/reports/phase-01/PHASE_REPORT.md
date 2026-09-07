# PHASE 01 REPORT — Monorepo Consolidation + Product Boundaries

Status: **PASS**

## Baseline at start
- repo: `C:\Projects\lectio`
- branch: `main`
- starting SHA: `bd19a9060b637b84f6d86c002cbf01513adf1e4b`
- dirty state: Phase 00 docs/tools + prior untracked evidence/logs; no Phase 01 product commits yet
- previous phase report read: `docs/xplore-program/reports/phase-00/PHASE_REPORT.md`

## What was implemented

1. Imported `lectio@0.6.0` from `lectio-legacy-20260805` → `packages/lectio` (package name remains `lectio`; rename deferred to Phase 02).
2. Wired frontend dependency `"lectio": "workspace:*"`; resolved as `link:../../../packages/lectio`.
3. Imported live Learn seams from Textbook agent `xplore` @ `d2cf2f27`:
   - `generation/component_lectio/**`
   - `units_dispatch.py`, `units_routes.py`, `pipeline_dispatch.py`
   - `retirement.py`, `canonical.py`, `canonical_routes.py`
   - `builder/service.py`, `planning/linkage.py`
   - migrations `20260904_0033`–`20260906_0035`
   - Component Lectio + runtime tests
   - supporting Learn modules (canonical_plan, component_selector, work_orders, lesson_document, checkpoints, leases, failure_policy, stage2_lanes, contracts/lesson_document, etc.)
4. Replaced Learn-owned overlaps with xplore versions while preserving Print: `builder/routes.py`, `learning/*`, `path_preparation.py`.
5. Extended `app.py` to keep Print `whole_lesson` worker and add `units_generation_router`.
6. Merged shared models carefully so Print page planners/writers stay green (SectionBlockPlan/PlannedBlock retained; IntentPlan appended; work-order repair fields from xplore; Print `qc_correction_hint` kept; component vs page resource candidates split).
7. Documented ownership in `CONSOLIDATION_OWNERSHIP_MAP.md`. Domain boundary checker already covers `packages/lectio`.

## Existing systems reused

| System | Classification | Existing path | Action |
|---|---|---|---|
| Component Lectio library | REFACTOR (import) | legacy → `packages/lectio` | Workspace package; no rename |
| Page Print package | REUSE_AS_IS | `packages/lectio-page` | Untouched |
| whole_lesson / page_objects | REUSE_AS_IS | Print generation | Kept |
| component_lectio generation | REUSE_AS_IS (import) | xplore → monorepo | Live Learn path |
| Builder frontend | REUSE_AS_IS | `frontend/src/lib/builder` | Kept |
| Builder backend routes | EXTEND / xplore-wins | `builder/routes.py` | Learn source-type cutover |
| v3_studio | REMOVE (later) | `generation/v3_studio/` | Documented duplicate; not live Learn |

## New subsystems/files requiring justification

| New area | Existing seam inspected | Why extension was insufficient |
|---|---|---|
| `packages/lectio` | npm `lectio@0.6.0` only | Need workspace source for Phase 02 `@lectio/learn` |
| `generation/component_lectio/` | Monorepo lacked live Learn | Import from xplore required |
| migrations 0033–0035 | Absent | Required for Component Lectio builder uniqueness |

## Files changed

Primary product paths (non-exhaustive): `packages/lectio/**`, backend Learn imports listed above, `app.py`, `core/config.py`, `core/database/models.py`, `v3_blueprint/planning/models.py` (+ IntentPlan merge), `v3_execution/models.py` (prior_validation_errors + Print qc_correction_hint), `resource_specs/component_candidates.py`, frontend `package.json` / lockfile, docs under `docs/xplore-program/`.

## Schema/migrations

- Imported Alembic revisions:
  - `20260904_0033_remove_generation_step_uniqueness`
  - `20260905_0034_add_component_lectio_builder_key`
  - `20260906_0035_repair_unit_capability_declarations`
- Model: `GenerationStepModel` uniqueness removed (append-only); `EditableLessonModel` Component Lectio unique index.

## Tests and verification

| Command / flow | Result | Evidence |
|---|---|---|
| `pnpm --filter @lectio/page test` | PASS 41 | page package |
| `pnpm --filter @lectio/page check` | PASS 0 errors | page package |
| backend Component Lectio + Builder + page planners/writers | PASS 93 | lifecycle/final_contract/prelive/runtime + builder + page_block_planner + page_object_writers |
| `packages/lectio` `pnpm test` | PASS 112 | includes previously timing-out export path now green in workspace |
| frontend document-version + LectioPageDocumentView + builder store/toolbar | PASS 15 | focused Page+Builder |
| `python tools/xplore-program/check_domain_boundaries.py` | PASS 0 violations | Print/Learn isolation |
| `python -m pytest tools/xplore-program/tests -q` | PASS 5 | domain guard + manifest schema |
| `pnpm why lectio` | `link:../../../packages/lectio` | workspace resolution |

## Acceptance gates

- [x] Page golden path works from the monorepo.
- [x] Component golden generation→Builder→edit→save→reload works from the monorepo (pytest Builder + Component Lectio lifecycle).
- [x] Workspace package resolution is local and deterministic.
- [x] Boundary guards pass.
- [x] No duplicate app/backend subsystem is retained without documented ownership (`CONSOLIDATION_OWNERSHIP_MAP.md`).

## Architecture deviations

1. Kept package name `lectio` (not `@lectio/learn`) — Phase 02 rename.
2. Retained `v3_studio` as documented REMOVE-later; live Learn is `component_lectio` only.
3. Merged xplore Learn work-order fields into monorepo Print models rather than wholesale replace (preserves `qc_correction_hint` / page SectionBlockPlan).
4. Split `resource_specs/candidates.py` (Print) vs `component_candidates.py` (Learn) instead of latest-wins.

## Known limitations / deferred

- `@lectio/learn` rename and print-export cleanup → Phase 02
- `v3_studio` deletion → later cleanup
- Unrelated dirty evidence/logs preserved
- Ending SHA remains `bd19a906…` (no commit requested)

## Final state

- ending SHA: `bd19a9060b637b84f6d86c002cbf01513adf1e4b` (uncommitted Phase 01 tree)
- dirty state: Phase 01 product imports + docs; prior evidence/logs; `.tmp/`
- generated artifacts: this report, updated PROGRAM_STATE / CURRENT_ARCHITECTURE / BASELINE_REUSE_MANIFEST / ownership map
- safe to proceed to next phase: **YES**

# Phase 01 execution plan (fresh from checkout after Phase 00 PASS)

## Goal
Co-locate Component Lectio package + live Learn generation seams into `C:\Projects\lectio` without breaking Print or Builder.

## Steps
1. Import `lectio@0.6.0` source from `lectio-legacy-20260805` → `packages/lectio` (keep package name `lectio`; no `@lectio/learn` rename — Phase 02).
2. Wire frontend `lectio: workspace:*`; pnpm install; prove local resolution.
3. Copy missing Learn modules from Textbook agent `xplore` @ d2cf2f27 into monorepo additively:
   - `generation/component_lectio/**`
   - `units_dispatch.py`, `units_routes.py`, `pipeline_dispatch.py`
   - `retirement.py`, `canonical.py`, `canonical_routes.py` (and support files if required)
   - `builder/service.py`
   - `planning/linkage.py`
   - Sept 2026 migrations if absent
   - Component Lectio + cutover tests
4. Wire routers in `app.py` only as needed; do not delete `whole_lesson` / `page_objects` / Print.
5. For overlapping files (builder/routes, learning/routes, path_preparation, app.py): reconcile by **xplore Learn ownership for Learn-specific seams**, preserve monorepo Print imports. Document every retained duplicate in CONSOLIDATION_OWNERSHIP_MAP.md.
6. Strengthen domain-boundary tests for workspace package.
7. Run Page golden path + Component Lectio tests in monorepo + boundary guards.
8. Report + update PROGRAM_STATE only on PASS.

## Explicit non-goals
- No `@lectio/learn` rename
- No deletion of Print
- No full wipe of v3_studio in this phase if still referenced by Print/studio routes — document REMOVE ownership instead
- No runtime/classes

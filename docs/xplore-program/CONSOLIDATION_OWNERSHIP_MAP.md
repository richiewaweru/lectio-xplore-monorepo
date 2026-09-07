# Consolidation Ownership Map — Phase 01

**Target:** `C:\Projects\lectio`  
**Sources:** Textbook agent `xplore` @ `d2cf2f27`, lectio-legacy @ `f71e78cd`

Classification key: keep = retain in monorepo; import = copied from source this phase; xplore-wins = replaced monorepo file with xplore Learn-owned version; print-keep = monorepo Print lineage retained; remove-later = documented duplicate not deleted yet.

| Subsystem | Canonical owner path | Decision | Notes |
|---|---|---|---|
| Component library package | `packages/lectio-learn` | import | From legacy `lectio@0.6.0`; frontend `workspace:*` |
| Page package | `packages/lectio-page` | keep | Print; must not import lectio |
| Unit/path planning routes | `apps/.../planning/` | keep + import `linkage.py` | Shared authoring |
| Print whole-lesson | `planning/whole_lesson/` | print-keep | Absent on xplore |
| Page object writers | `generation/page_objects/` | print-keep | Absent on xplore |
| Component Lectio generation | `generation/component_lectio/` | import | From xplore; was missing |
| Units generation dispatch | `units_dispatch.py`, `units_routes.py`, `pipeline_dispatch.py` | import | From xplore |
| Canonical Learn projections | `canonical.py`, `canonical_routes.py` | import | From xplore |
| Retirement stubs | `retirement.py` | import | Available; v3_studio still also present |
| Builder service | `builder/service.py` | import | Component Lectio → Builder |
| Builder routes | `builder/routes.py` | xplore-wins | Learn source-type cutover |
| Learning pack API | `learning/*` | xplore-wins | component_lectio filter |
| Path preparation | `generation/path_preparation.py` | xplore-wins | pipeline=component_lectio |
| Blueprint Learn helpers | `canonical_plan.py`, `component_selector.py`, `work_orders.py`, models/persistence (xplore) | import / xplore-wins | Required by component_lectio |
| Execution Learn runtime | `lesson_document.py`, checkpoints, leases, failure_policy, lectio_validation, compile_orders | import / xplore-wins | Required by component_lectio |
| App composition root | `app.py` | EXTEND | Keeps Print worker + adds `units_generation_router` |
| Pre-cutover v3_studio | `generation/v3_studio/` | remove-later | Still present for Print/studio history; not live Learn. Ownership: Print/legacy Studio — do not use for new Learn. |
| Frontend Builder UI | `frontend/src/lib/builder/` | keep | Monorepo Builder retained |
| Migrations 0033–0035 | `migrations/versions/202609*` | import | Component Lectio builder uniqueness + capability repair |

## Duplicate retention (explicit)

1. **`v3_studio` + `component_lectio`:** both exist. Live Learn traffic must use `component_lectio` via Units. `v3_studio` retained until a later cleanup phase so Print/studio evidence paths are not destroyed mid-consolidation.
2. **`whole_lesson` vs Component Learn:** dual realization by design (Print vs Learn), not a duplicate subsystem.
3. **npm vs workspace lectio:** resolved — only workspace `packages/lectio-learn`.

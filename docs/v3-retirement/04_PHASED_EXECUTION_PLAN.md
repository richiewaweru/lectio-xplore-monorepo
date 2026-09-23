# Phased Execution Plan

## Phase 0 — Baseline and branch

### Goal
Establish a reproducible native baseline before touching architecture.

### Actions
1. Sync `main`.
2. Create dedicated cleanup branch.
3. Record HEAD SHA in runbook.
4. Inspect repository test/build scripts rather than guessing commands.
5. Run the smallest reliable backend + frontend baseline suites.
6. Run or replay one known native Unit lesson through as much of the current flow as practical.
7. Capture current repository searches:
   - imports of `v3_execution`;
   - imports of `v3_blueprint`;
   - imports/calls to old section writer;
   - frontend `$lib/api/v3`;
   - `/api/v1/v3` references;
   - `V3*` active components.

### Gate 0
Do not change architecture until:
- app imports/starts;
- baseline tests chosen for the migration are green or existing failures are recorded with evidence;
- one current native preparation/Teaching Plan flow can be identified;
- runbook contains HEAD and baseline evidence.

---

## Phase A — Dependency map and ownership classification

### Goal
Complete the MOVE/DELETE/SPLIT classification before major movement.

### Actions
1. Trace current native roots:
   - Unit preparation;
   - Structural Plan;
   - item generation;
   - Teaching Plan;
   - Learn realization;
   - Print realization;
   - visual paths;
   - retry/status paths.
2. Build caller graph for every `v3_execution` module.
3. Build caller graph for every `v3_blueprint` module.
4. Split current vs legacy routes inside `v3_studio/router.py`.
5. Map frontend current Unit/Print screens to their APIs/components.
6. Update `03_MOVE_DELETE_MANIFEST.md` with exact evidence.

### Gate A
Pass only when:
- every production `v3_execution` file is classified;
- every production `v3_blueprint` file is classified;
- every production `v3_studio` route is classified current or legacy;
- every active frontend `V3`/Studio surface is classified;
- no deletion is based on naming alone.

Commit Phase A documentation if useful.

---

## Phase B — Extract shared/current execution infrastructure

### Goal
Make current native code stop depending on legacy execution ownership.

### Recommended order

#### B1. Structured LLM/model configuration
Move current generic:
- structured provider helpers;
- retry/no-output helper definitions;
- model settings/slots;
- generic timeouts if current.

Target `infra/authoring` / `infra/execution` ownership.

Update current callers first, tests second, delete old re-export last.

#### B2. Item generation
Move current item generator + item-specific errors/models into `curriculum/items`.

Update native preparation/Teaching Plan pipeline to use the new module.

#### B3. Visual execution
Move visual executor + current visual work-order models into `media/generation`.

Update:
- Learn figure pipeline;
- Print visual dispatch;
- visual QC/diagnostics that are current.

### Migration method
For each move:
1. copy/move code without semantic rewrite;
2. update imports;
3. run targeted tests;
4. search for remaining current import of old path;
5. remove old implementation or leave a temporary thin re-export only if needed for unfinished legacy callers;
6. do not proceed until native callers all use current path.

### Gate B
Required:
- current `infra/authoring` no longer imports `v3_execution.llm_helpers`;
- current native item generation imports current curriculum item module;
- current Learn/Print media paths import current media executor;
- targeted tests green;
- application startup green;
- no behavior change demonstrated by diff/test evidence.

Commit Phase B.

---

## Phase C — Rehome planning from `v3_blueprint`

### Goal
Make the current planning domain self-describing.

### Move current planning ownership to `curriculum/planning` (or closest existing current domain):
- StructuralPlan and current planning models;
- planning persistence/state;
- structural planner;
- objective ownership;
- skeleton catalogue;
- knowledge classifier only if current.

### Important
Do not rename persisted JSON fields or database columns merely to remove "v3" unless they are purely internal and migration-safe. Namespace cleanup does not require data migration.

### Gate C
Pass only when:
- `application/unit_lesson/*` has no active import from `v3_blueprint`;
- current Teaching Plan/preparation path has no active import from `v3_blueprint`;
- app starts;
- planning tests pass;
- prepare -> structural review still works;
- search shows only legacy code may still import `v3_blueprint`.

Commit Phase C.

---

## Phase D — Extract native HTTP and frontend ownership from V3 Studio

### Goal
Separate product-current native interfaces from legacy Studio.

### Backend
Create current routers under `application/unit_lesson` or other current domains for:
- preparation/status;
- Structural Plan approval/retry;
- Teaching Plan read/approve/reject;
- Learn/Print realization;
- native retry;
- current visual retry if applicable;
- current native document editing endpoints if they belong here.

Thin compatibility route adapters are allowed temporarily, but business logic must move to current handlers.

### Frontend
Move current calls out of `$lib/api/v3.ts` into current modules, e.g.:
- `lesson-planning.ts`;
- `teaching-plan.ts`;
- `realizations.ts`;
- Print document API module.

Rename current components:
- `V3PlanPreview` -> `StructuralPlanPreview`;
- `V3PlanActions` -> `StructuralPlanActions`;
- any current editor/preview component moved out of `studio` directories.

### Gate D
Required:
- current Unit Plan page no longer imports `$lib/api/v3`;
- current Learn/Print Unit pages no longer require legacy Studio API modules for native actions;
- native backend business logic is not housed in the legacy Studio router;
- frontend tests/build pass;
- native route tests pass;
- compatibility adapters, if present, are explicitly listed for final removal.

Commit Phase D.

---

## Phase E — Delete the legacy V3 execution island

### Goal
Physically remove retired generation architecture.

### Delete only after zero-caller proof
Expected deletion candidates include:
- `v3_execution/executors/section_writer.py`;
- section-writer prompt;
- legacy Stage 2 lanes;
- old V3 generation runner;
- question writer if no current caller remains;
- compile-orders;
- old section/pack assembly;
- legacy repair endpoints based on `execute_section`;
- obsolete DTOs/models used only by deleted routes;
- legacy tests/experiments proving deleted behavior.

### Backend route cleanup
Remove legacy:
- standalone V3 generation start/streaming;
- blueprint execution back half;
- card/component repair through old section writer;
- pack/variant routes no longer used by current product.

### Gate E
Required searches should show:
- no production import of old section writer;
- no production call to `execute_section`;
- no legacy Stage 2 creation route reachable from current app;
- application imports cleanly after actual files are deleted;
- backend test suite subset passes.

Commit Phase E.

---

## Phase F — Delete legacy frontend Studio/V3 product surfaces

### Goal
Remove frontend architecture that no longer represents the product.

### Actions
1. Delete old standalone Studio creation routes after proving no current navigation depends on them.
2. Delete old V3 generation details screens.
3. Delete old V3 input/booklet/repair components.
4. Move any remaining current Print viewer/editor first.
5. Shrink/delete `$lib/api/v3.ts`.
6. Remove dead types/tests/styles.

### Gate F
Pass only when:
- active Unit/Learn/Print pages build without legacy Studio code;
- navigation has no broken links;
- current Print editor/viewer still opens;
- frontend tests pass;
- production source search contains no unexplained `V3` naming.

Commit Phase F.

---

## Phase G — Namespace closeout and dependency proof

### Goal
Make the repository tell the truth.

Run global searches similar to:

```text
rg "v3_execution|v3_blueprint|v3_studio|V3[A-Z]" \
  apps/textbook-agent/backend/src \
  apps/textbook-agent/frontend/src
```

Every remaining result must be one of:
- migration/history docs;
- deliberate persisted compatibility nomenclature;
- explicitly justified compatibility adapter.

Prefer zero active-code results.

Update imports, comments, test names, docs, and file locations so old V3 vocabulary is not casually retained.

### Gate G
No unexplained active code remains under V3 naming.

---

## Phase H — Full native proof

Execute `06_E2E_ACCEPTANCE.md`.

Do not declare completion based only on static tests.

Commit final proof/closeout artifacts and write `09_CLOSEOUT_REPORT_TEMPLATE.md`.

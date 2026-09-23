# MOVE / DELETE Manifest

This file is both a starting classification and a work artifact.

Casa must update the **Evidence**, **Final destination**, and **Disposition** columns after inspecting HEAD.

Legend:

- `MOVE` = current behavior; rehome under current domain ownership.
- `DELETE` = legacy-only after zero-caller proof.
- `SPLIT` = mixed current + legacy responsibilities; extract current portion first.
- `VERIFY` = insufficient evidence; investigate before action.

---

## Backend: `v3_execution`

| Current path / area | Initial disposition | Target ownership | Evidence / gate |
|---|---|---|---|
| `v3_execution/llm_helpers.py` | MOVE | `infra/authoring/*` or `infra/llm/*` | Current `infra/authoring/engine.py`, curriculum agents, Teaching/Form agents import it |
| `v3_execution/config/*` | MOVE/SPLIT | `infra/authoring/model_policy` + `infra/execution` | Current authoring/planning code imports model settings/slots/timeouts |
| `v3_execution/executors/item_executor.py` | MOVE | `curriculum/items/generator.py` | Current native Stage 2 uses item generation before Teaching Plan |
| `v3_execution/executors/item_errors.py` | MOVE | `curriculum/items/errors.py` | Current native failure policy imports item generation error |
| `v3_execution/executors/visual_executor.py` | MOVE | `media/generation/executor.py` | Current Learn figure and Print visual paths call it |
| visual models in `v3_execution/models.py` | SPLIT/MOVE | `media/generation/models.py` | Move only models required by current media path |
| item models in `v3_execution/models.py` | SPLIT/MOVE | current item domain if still used | Prove callers |
| `v3_execution/executors/section_writer.py` | DELETE | none | Legacy Studio/runtime calls only; current Learn/native Print do not import it |
| `v3_execution/prompts/section_writer.py` | DELETE | none | Delete with section writer |
| `v3_execution/runtime/stage2_lanes.py` | DELETE candidate | none | Legacy back half |
| `v3_execution/runtime/runner.py` | SPLIT/DELETE candidate | none or extract generic event helper | Old generation/SSE runtime; inspect any surviving generic helper |
| `v3_execution/executors/question_writer.py` | DELETE candidate | none | No known external current caller; prove zero-caller after old runtime removal |
| `v3_execution/executors/answer_key_generator.py` | VERIFY | current Print if required, otherwise delete | Do not assume |
| `v3_execution/compile_orders.py` | DELETE candidate | none | Known caller is old V3 execution/router; prove |
| `v3_execution/assembly/section_builder.py` | DELETE candidate | none | Prove zero-current-callers |
| `v3_execution/assembly/pack_builder.py` | DELETE candidate | none | Prove zero-current-callers |
| `v3_execution/runtime/lesson_document.py` | VERIFY | `document/` only if current | Inspect |
| `v3_execution/runtime/lanes.py` | VERIFY/DELETE candidate | `infra/execution` only if generic/current | Inspect |
| `v3_execution/runtime/writer_schema.py` | VERIFY | `infra/authoring` only if current | Inspect |

---

## Backend: `v3_blueprint`

These are more likely **current planning code with an obsolete namespace** than dead architecture.

| Current path / area | Initial disposition | Target ownership | Evidence / gate |
|---|---|---|---|
| `v3_blueprint/planning/models.py` | MOVE | `curriculum/planning/models.py` | Current Unit preparation/status imports `StructuralPlan` and related models |
| `v3_blueprint/planning/persistence.py` | MOVE | `curriculum/planning/persistence.py` | Current status/retry/router use chunked preparation state |
| `v3_blueprint/planning/structural_planner.py` | MOVE | `curriculum/planning/structural_planner.py` | Current native planning path |
| `v3_blueprint/planning/objective_ownership.py` | MOVE | `curriculum/planning/objective_ownership.py` | Current Unit preparation imports |
| `v3_blueprint/skeletons.py` | MOVE | `curriculum/planning/skeletons.py` | Current Unit preparation/app initialization uses |
| `v3_blueprint/knowledge_classifier.py` | VERIFY/MOVE | `curriculum/planning` if current | Prove callers |
| old ProductionBlueprint-only compiler/types | SPLIT/DELETE candidate | none | Preserve only if current native path still needs them |

**Gate:** no current Unit/native code may import `v3_blueprint` after the planning move.

---

## Backend: mixed `v3_studio` HTTP ownership

| Current path / area | Disposition | Target |
|---|---|---|
| native preparation/structural approval handlers | MOVE | `application/unit_lesson/routes/*` |
| Teaching Plan read/approve/reject | MOVE | `application/unit_lesson/routes/teaching_plan.py` |
| `realize-learn` | MOVE | `application/unit_lesson/routes/realizations.py` |
| `realize-print` | MOVE | `application/unit_lesson/routes/realizations.py` |
| `retry-native` | MOVE | `application/unit_lesson/routes/retry.py` |
| current visual retry callback/dispatch endpoints | MOVE if product-current | `media` or `unit_lesson` current router |
| native document read/edit endpoints | MOVE if current | current Print/document router |
| `/generate/start` legacy Studio generation | DELETE after frontend legacy removal |
| component/card repair via old `execute_section` | DELETE |
| old blueprint generation/assembly endpoints | DELETE |
| old standalone pack/variant routes | DELETE if no current native caller |

**Rule:** split the giant router first. Do not leave native logic behind merely because the URL historically begins with `/v3`.

---

## Frontend

| Current area | Disposition | Target |
|---|---|---|
| current Unit lesson plan API calls in `$lib/api/v3.ts` | MOVE | `lesson-planning.ts`, `teaching-plan.ts`, `realizations.ts` or equivalent |
| current Print document API calls in `$lib/api/v3.ts` | MOVE | current Print/document API module |
| current Unit components named `V3PlanPreview/Actions` | RENAME/MOVE | `StructuralPlanPreview/Actions` if current |
| current Print editor under `components/studio` | MOVE | `lib/print/editor/*` if current |
| `routes/studio/+page.svelte` old standalone generation | DELETE candidate | none |
| `routes/studio/generations/[id]` | DELETE candidate | none |
| old V3 booklet/issue/input components | DELETE if legacy-only | none |
| `routes/studio/print/[id]` | VERIFY | move current Print viewer if native; otherwise delete |
| builder `concept-cards` / `pack-items` APIs pointing to `/v3` | VERIFY | determine if current product still supports them |

---

## Mandatory manifest completion rule

Before Phase E deletion begins, every entry under:

```text
backend/src/v3_execution
backend/src/v3_blueprint
backend/src/print/http/v3_studio
frontend/src/routes/studio
frontend/src/lib/api/v3.ts
frontend/src/lib/print/components/studio
```

must be classified.

No unclassified production file may remain simply because it was difficult to understand.

---

## HEAD classification (802b4f98) — completed 2026-09-23

Re-audit of production imports under `apps/textbook-agent/backend/src` and frontend callers. The pack's initial guesses were updated where HEAD differed.

### `v3_execution` (40 files)

MOVE: `llm_helpers.py` → `infra/authoring/structured_provider.py`; `executors/item_executor.py` + `item_errors.py` + `item_diagnostics.py` + `prompts/item_prompt.py` → `curriculum/items/*`; `executors/visual_executor.py` + `prompts/visual_executor.py` → `media/generation/*`; `runtime/retry_runner.py` → `infra/execution/retry_runner.py`.

SPLIT: `config/{__init__,models,timeouts,retries}.py` (keep current nodes/keys, drop writer nodes later); `models.py` (keep visual types); `prompts/formatting.py`; `runtime/validation.py`.

DELETE after Phase E zero-caller proof: `section_writer` executor+prompt, `question_writer` executor+prompt, `answer_key_generator` + `prompts/answer_key.py` (native Print uses `document_assembly.build_answer_key_block`), `runtime/{runner,stage2_lanes,lanes,lesson_document,writer_schema,events,lectio_validation,checkpoints,leases,failure_policy}.py`, `compile_orders.py`, `assembly/{section,pack}_builder.py`, `component_aliases.py`, `booklet_status.py`, `config/{concurrency,answer_key_node,policy}.py`, package `__init__.py`.

Correction vs pack: `answer_key_generator` is DELETE (only `runner.py` calls it). `runner.py` is DELETE (Studio `/generate/start` only). `lesson_document.py` is DELETE (zero current callers).

### `v3_blueprint` (19 files)

MOVE: `planning/models.py`, `planning/persistence.py`, `planning/objective_ownership.py`, `skeletons.py` → `curriculum/planning/*`.

SPLIT: root `models.py` — keep `LessonMode`/`ResourceType` used by `learn/generation/contracts.py`; delete `ProductionBlueprint` with compiler.

DELETE: `planning/structural_planner.py` (native planner is `curriculum.agents.run_path_structural_planner`), `knowledge_classifier.py` (zero callers), `compiler.py`, `work_orders.py`, `planning/{assembler,retry,validators,section_expander,canonical_plan,work_orders,component_selector}.py`, `shadow.py`, `validators.py`, package inits.

Correction vs pack: `structural_planner.py` is DELETE, not MOVE.

### `v3_studio` routes

MOVE native handlers: chunked plan/status/approve, lesson-approach get/approve/reject, realize-learn, realize-print, retry-native, visuals callback/retry, document GET, lectio-document GET/PUT, export PDF, generation detail (used by current print).

DELETE after frontend cleanup: `/signals`, `/narrow`, `/propose-intent`, `/chunked/plan/start` (already 410), pack/card/item library, `/generate/start`, traces, print-snapshot, supplements (410), component patch, card repair, per-visual regenerate, blueprint adjust.

VERIFY: `regenerateChunkedPlan` (handler always 409; frontend still calls), `page-blocks` PATCH (native, no FE), `retry-section` (native adapter vs leftover Studio).

### Frontend

MOVE/RENAME: unit plan `$lib/api/v3` helpers → lesson-planning/teaching-plan/realizations; `V3PlanPreview`/`V3PlanActions`; `PrintDocumentEditor` + `LectioPageDocumentView`; `routes/studio/print/[id]` is the current Print editor.

SPLIT then strip: `routes/studio/+page.svelte` is still the unit-prep progress host (`unit-workspace` navigates here after prepare).

DELETE: standalone generations booklet, `V3InputSurface`, canvas/booklet/blueprint leftovers, unused `$lib/api/v3` wrappers.

Unit learn page does **not** import `$lib/api/v3` (uses `$lib/api/units`).

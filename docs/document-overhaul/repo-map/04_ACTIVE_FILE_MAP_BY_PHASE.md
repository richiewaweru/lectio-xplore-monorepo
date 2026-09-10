# Active File Map by Phase

Legend:
- **EDIT**: expected active modification
- **REVIEW**: must be opened/searched before deciding
- **NEW**: recommended target file/folder
- **DELETE**: candidate once references are removed
- **KEEP**: preserve behavior unless new architecture requires a narrow change

## A — Shared instruction
- EDIT `backend/src/curriculum/teaching_plan/models.py`
- EDIT `backend/src/curriculum/teaching_plan/{service,revisions,consumers,coverage,projections}.py`
- REVIEW `backend/src/curriculum/teaching_plan/{compatibility,instance_ids}.py`
- EDIT `backend/src/curriculum/{agents,prompts}.py`
- EDIT `packages/lectio-contracts/src/{actions,teaching-view,index}.ts`
- MOVE OWNERSHIP `packages/lectio-page/contracts/intent-catalogue.v1.json`

## B — Document vocabulary
- NEW `backend/src/document/{__init__,models,validation}.py`
- REVIEW `print/generation/page_blocks.py`
- REVIEW `print/generation/whole_lesson/form_plan.py`
- REVIEW `packages/lectio-page/contracts/{lectio-document-v2.schema.json,object-catalogue.v1.json}`
- REPLACE `learn/contracts/lesson_document.py`

## C — Print extraction
- EDIT/REVIEW `print/generation/{selection_snapshot,work_orders,page_blocks,page_projections}.py`
- EDIT/REVIEW `print/generation/whole_lesson/{form_agent,form_plan,prompt_render,executor}.py`
- KEEP `print/rendering/**`
- KEEP/ADAPT `packages/lectio-page/**`
- KEEP PRINT-ONLY `packages/lectio-page/src/lib/print/base-print.css`

## D — Path admission
- KEEP/EDIT `application/unit_lesson/{realization_contracts,realizations,dispatch,status}.py`
- REVIEW/RETIRE `application/unit_lesson/dual_native.py`
- EDIT `curriculum/routes.py`
- EDIT corresponding frontend Unit API/types/actions

## E — Realizers
- NEW `print/generation/document_realizer.py`
- NEW `learn/generation/document_realizer.py`
- REPLACE/SHRINK `print/generation/selection_snapshot.py`
- REPLACE `learn/generation/native_selection.py`
- REVIEW `infra/authoring/capability_selector.py`
- REVIEW `print/resources/selection.py`
- REVIEW `learn/resources/selection.py`

## F — Learn production
- EDIT `learn/generation/{native_production,native_execution,work_orders,ordered_assemble,canonical}.py`
- REPLACE `learn/contracts/lesson_document.py`
- DELETE AFTER CUTOVER `learn/generation/component_lectio/**`
- REVIEW `learn/generation/authoring_adapter.py`

## G — Interactions
- KEEP/SHRINK `learn/generation/{interaction_writer,activity_authoring}.py`
- KEEP/SHRINK `learn/runtime/**`
- MOVE retained UI from `packages/lectio-learn/src/lib/learn/**`
- DELETE unsupported interaction renderers/contracts
- DELETE asset-heavy unsupported interaction paths

## H — Print realization
- EDIT `print/generation/{native_production,work_orders}.py`
- EDIT `print/generation/whole_lesson/**` as required
- KEEP/ADAPT `print/rendering/**`
- KEEP/ADAPT `packages/lectio-page/**`

## I — Learn editor
- EDIT `frontend/src/lib/learn/student/{StudentLessonShell,OrderedBlockList}.svelte`
- EDIT `frontend/src/lib/learn/student/student-shell.ts`
- EDIT `frontend/src/lib/learn/authoring/**`
- NEW `frontend/src/lib/learn/document/**`
- EDIT `frontend/src/routes/learn/lessons/[id]/+page.svelte`
- EDIT `frontend/src/routes/learn/instances/[instanceId]/+page.svelte`

## J — Prompts/writers
- EDIT `curriculum/prompts.py`
- EDIT `print/generation/prompts.py`
- EDIT `print/generation/whole_lesson/prompt_render.py`
- NEW generic document writer modules under `document/` or each path owner
- KEEP only retained interaction writer prompts
- DELETE component-specific ordinary writer prompt/export machinery

## K — Persistence/releases
- REVIEW/EDIT `core/database/models.py`
- REVIEW/EDIT `infra/database/**`
- EDIT `learn/authoring/builder/{routes,service}.py`
- EDIT `learn/publishing/publish_validation.py`
- KEEP/ADAPT `learn/publishing/**`
- KEEP/ADAPT `print/generation/whole_lesson/repository.py`

## L — Frontend path UX
- EDIT `frontend/src/routes/units/**`
- EDIT `frontend/src/lib/curriculum/**`
- EDIT `frontend/src/lib/{print,learn}/**`
- EDIT `frontend/src/lib/api/**`
- KEEP dashboard/auth/application shell unless directly coupled to deleted model

## M — Hard delete
- DELETE `learn/generation/component_lectio/**`
- DELETE retired ordinary capability code in `packages/lectio-learn/**`
- DELETE Learn Print-mode helpers
- DELETE video/simulation/unsupported media paths
- DELETE obsolete old generation tests/prompts/exports/adapters
- DO NOT preserve old lesson read/migration compatibility

## N — Repo/package cleanup
- EDIT root `package.json`, lock/workspace only as required
- EDIT `apps/textbook-agent/agents/project.md`
- EDIT `docs/architecture/CURRENT_SYSTEM.md`
- EDIT architecture guards/tests
- DELETE `packages/lectio-learn` if no independent consumer remains
- KEEP `packages/lectio-page`
- KEEP/REFRAME `packages/lectio-contracts`

## O — Verification
- ADD focused tests under backend/frontend/package test owners
- UPDATE zero-legacy/domain guard tooling
- ADD final run report under `docs/project/runs/`

# Active File Map

Open and trace these before editing. Search all callers/consumers of every changed symbol.

## Shared prompt infrastructure

```text
apps/textbook-agent/backend/resources/prompts/manifest.yaml
apps/textbook-agent/backend/src/core/prompts/loader.py
apps/textbook-agent/backend/src/core/prompts/
apps/textbook-agent/backend/src/curriculum/prompts.py
```

## Teaching Plan / learner actions

```text
apps/textbook-agent/backend/resources/lesson-approach-planner-v2.txt
apps/textbook-agent/backend/src/curriculum/teaching_plan/models.py
apps/textbook-agent/backend/src/curriculum/teaching_plan/service.py
apps/textbook-agent/backend/src/curriculum/teaching_plan/coverage.py
apps/textbook-agent/backend/src/curriculum/agents.py
```

## Shared document composition/writing

```text
apps/textbook-agent/backend/src/document/models.py
apps/textbook-agent/backend/src/document/composition.py
apps/textbook-agent/backend/src/document/composer.py
apps/textbook-agent/backend/src/document/writer.py
apps/textbook-agent/backend/resources/prompts/document-composer-v1.txt
apps/textbook-agent/backend/resources/prompts/document-writer-v1.txt
```

## Learn realization/interactions

```text
apps/textbook-agent/backend/src/learn/generation/native_production.py
apps/textbook-agent/backend/src/learn/generation/interaction_writer.py
apps/textbook-agent/backend/src/learn/generation/figure_pipeline.py
apps/textbook-agent/backend/src/learn/interactions/action_map.py
apps/textbook-agent/backend/src/learn/interactions/registry.py
apps/textbook-agent/backend/src/learn/runtime/
apps/textbook-agent/backend/src/application/unit_lesson/realize_learn_handoff.py
apps/textbook-agent/backend/src/learn/generation/units_routes.py
```

## Print realization

```text
apps/textbook-agent/backend/src/print/generation/native_production.py
apps/textbook-agent/backend/src/print/generation/composition_bridge.py
apps/textbook-agent/backend/src/print/generation/task_treatments.py
apps/textbook-agent/backend/src/print/generation/work_orders.py
apps/textbook-agent/backend/src/print/generation/authoring_adapter.py
apps/textbook-agent/backend/src/print/generation/whole_lesson/executor.py
apps/textbook-agent/backend/src/print/generation/whole_lesson/repository.py
apps/textbook-agent/backend/src/print/http/v3_studio/router.py
```

## Figure serving

```text
apps/textbook-agent/backend/src/app.py
apps/textbook-agent/backend/src/learn/generation/figure_pipeline.py
apps/textbook-agent/frontend/src/lib/learn/document/resolve-asset.ts
```

## Learn document UI

```text
apps/textbook-agent/frontend/src/lib/learn/document/
apps/textbook-agent/frontend/src/lib/learn/interactions/
apps/textbook-agent/frontend/src/routes/builder/[id]/+page.svelte
apps/textbook-agent/frontend/src/routes/units/[id]/+page.svelte
apps/textbook-agent/frontend/src/routes/learn/
```

## Print viewer/editor target

```text
apps/textbook-agent/frontend/src/routes/studio/print/[id]/+page.svelte
apps/textbook-agent/frontend/src/lib/print/components/studio/LectioPageDocumentView.svelte
apps/textbook-agent/backend/src/print/generation/whole_lesson/repository.py
apps/textbook-agent/backend/src/print/http/v3_studio/router.py
```

Do not build native Print editing on `/builder/print/[id]`; that route is a LearnDocument print view, not the native LectioDocument v2 artifact.

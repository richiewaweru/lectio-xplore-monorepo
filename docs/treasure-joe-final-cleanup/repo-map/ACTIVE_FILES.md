# Active Files

## A — learner actions

```text
backend/resources/policies/learner-actions.yaml
backend/resources/policies/learn-action-map.yaml
backend/resources/policies/print-action-map.yaml
backend/src/core/policies/loader.py
backend/src/curriculum/teaching_plan/models.py
backend/src/print/generation/whole_lesson/teaching_agent.py
backend/src/print/generation/whole_lesson/prompt_render.py
backend/tests/core/policies/test_action_maps.py
backend/tests/print_learn/test_learner_action_policy.py
```

## B — interaction selection

```text
backend/resources/prompts/interaction-selection.md
backend/src/learn/generation/native_production.py
backend/src/learn/interactions/action_map.py
backend/src/core/policies/loader.py
backend/resources/policies/learn-action-map.yaml
```

## C — v1 Learn salvage

```text
backend/src/learn/generation/native_production.py
backend/src/learn/generation/native_selection.py
backend/src/learn/generation/work_orders.py
backend/src/learn/generation/ordered_assemble.py
backend/src/learn/contracts/lesson_document.py
backend/tests/learn/
backend/tests/print_learn/
```

Search:
`build_closed_learn_production`, `build_closed_learn_production_async`,
`host_interaction_blocks_for_builder`, `closed_learn_selection`,
`explanation-block`, `LessonDocument v1`.

## D — Unit Learn proof

```text
frontend/src/routes/units/[id]/+page.svelte
frontend/src/lib/api/units.ts
backend/src/learn/generation/units_routes.py
backend/src/application/unit_lesson/realize_learn_handoff.py
backend/src/learn/generation/native_production.py
frontend/src/routes/builder/
frontend/src/lib/learn/interactions/
backend/src/learn/runtime/
```

## E — Print PDF proof

```text
frontend/src/lib/print/components/studio/PrintDocumentEditor.svelte
frontend/src/routes/studio/print/[id]/+page.svelte
backend/src/print/http/v3_studio/router.py
backend/src/print/generation/whole_lesson/repository.py
packages/lectio-page/
```

## F — finality

```text
package.json
docs/generation-closeout/tracking/STATE.json
docs/generation-closeout/tracking/PHASE_*.md
docs/generation-closeout/verification/FINAL_ACCEPTANCE_MATRIX.md
```

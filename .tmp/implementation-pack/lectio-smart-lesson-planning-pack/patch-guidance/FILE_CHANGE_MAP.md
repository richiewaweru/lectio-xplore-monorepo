# File Change Map

This is a map, not permission to edit blindly. Search downstream references before changing contracts.

## Flow ownership

Likely active files:

```text
apps/textbook-agent/backend/resources/skeletons.yaml
apps/textbook-agent/backend/src/v3_blueprint/skeletons.py
apps/textbook-agent/backend/src/application/unit_lesson/prepare.py
apps/textbook-agent/backend/resources/path-structural-planner-v1.txt
apps/textbook-agent/backend/src/curriculum/agents.py
apps/textbook-agent/backend/src/curriculum/models.py
```

Target:

- skeleton preview returns recommendation + closed slot catalogue;
- planner selects legal flow;
- prepare validates flow rather than exact equality to recommendation;
- instance IDs remain code-owned.

## Teaching Plan contract

```text
apps/textbook-agent/backend/src/curriculum/teaching_plan/models.py
apps/textbook-agent/backend/src/print/generation/whole_lesson/teaching_agent.py
apps/textbook-agent/backend/src/print/generation/whole_lesson/validation.py
apps/textbook-agent/backend/src/print/generation/whole_lesson/prompt_render.py
apps/textbook-agent/backend/resources/lesson-approach-planner-v2.txt
apps/textbook-agent/backend/resources/prompts/learner-action-policy.md
```

Target:

- add formative vs assessment task ownership;
- remove rule that *all* response actions require approved source;
- preserve strict approved-source contract for assessment tasks.

## New shared content/task ownership

Preferred ownership location:

```text
apps/textbook-agent/backend/src/curriculum/lesson_sourcebook/
apps/textbook-agent/backend/src/curriculum/shared_tasks/
```

Equivalent shared package name is acceptable if it does not belong to Print or Learn.

Expected modules:

```text
models.py
service.py
validation.py
prompts.py (or canonical prompt loader use)
```

## Document writing

```text
apps/textbook-agent/backend/src/document/writer.py
apps/textbook-agent/backend/resources/prompts/document-writer.md
apps/textbook-agent/backend/src/document/composer.py
```

Composer likely requires no semantic change.

Writer should receive exact sourcebook entries and, when needed, committed neighbour summaries/content.

## Learn

```text
apps/textbook-agent/backend/src/learn/generation/native_production.py
apps/textbook-agent/backend/src/learn/generation/interaction_writer.py
apps/textbook-agent/backend/resources/prompts/interaction-writer.md
apps/textbook-agent/backend/resources/prompts/interaction-selection.md
```

`interaction-selection.md` likely remains unchanged.

Interaction authoring should consume SharedTaskSpec and preserve content/evaluation.

## Print

```text
apps/textbook-agent/backend/src/print/generation/task_treatments.py
apps/textbook-agent/backend/src/print/generation/document_realizer.py
apps/textbook-agent/backend/src/print/generation/composition_bridge.py
apps/textbook-agent/backend/src/print/generation/authoring_adapter.py
apps/textbook-agent/backend/resources/prompts/print-realization.md
```

Keep task-treatment mapping Print-owned. Feed it SharedTaskSpec instead of requiring every response task to originate from an approved item.

## Review

New shared ownership, e.g.:

```text
apps/textbook-agent/backend/src/curriculum/lesson_review/
  models.py
  deterministic.py
  reviewer.py
  repair.py
```

The reviewer must be path-aware in input but not path-owned in code.

## Prompt manifest

```text
apps/textbook-agent/backend/resources/prompts/manifest.yaml
apps/textbook-agent/backend/src/core/prompts/loader.py
apps/textbook-agent/backend/tests/core/prompts/
```

Add/version the new prompt IDs. Update hash/version tests through the canonical mechanism; do not create parallel prompt loading.

## Persistence

Inspect current whole-lesson repository/state ownership before adding tables. Prefer revision-bound JSON artifacts/checkpoints when existing generation persistence can safely own them.

Required reloadable artifacts:

```text
flow choice
sourcebook
shared task registry
coherence report(s)
repair events
```

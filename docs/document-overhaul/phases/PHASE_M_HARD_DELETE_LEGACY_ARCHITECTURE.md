# Phase M — Hard Delete Legacy Architecture

## Goal
Perform the clean cut: remove code, contracts, tests and routes whose only purpose is the old ordinary content-component system or unsupported media.

## Open these active files first
- `apps/textbook-agent/backend/src/learn/generation/component_lectio/`
- `apps/textbook-agent/backend/src/learn/generation/native_selection.py`
- `apps/textbook-agent/backend/src/learn/generation/authoring_adapter.py`
- `apps/textbook-agent/backend/src/learn/contracts/lesson_document.py`
- `packages/lectio-learn/`
- `apps/textbook-agent/backend/contracts/`
- `apps/textbook-agent/backend/src/core/database/migrations/versions/`
- `apps/textbook-agent/backend/src/infra/database/migrations/versions/`

## Implementation tasks
- Delete `component_lectio` after all active imports are gone.
- Delete ordinary content capability registry/selection/schema/writer code.
- Delete old SectionContent/template/content-component contracts.
- Delete Learn-owned Print helpers such as RuledLines and print hints.
- Delete video/simulation/unsupported-media code from active architecture.
- Delete obsolete tests, docs and exports that assert old behavior; do not delete historical migrations needed for a clean DB upgrade unless the database migration strategy is intentionally rebased.
- Remove legacy source-type references such as `component_lectio` from active models/routes.
- Run zero-reference searches before finishing.

## Expected outputs
- `legacy deletion report`
- `zero-reference search evidence`
- `updated current architecture docs`

## Acceptance gate
Fresh production code contains no imports/references to the old ordinary component system. A repository search for the retired production identifiers returns only explicitly archived historical documentation, or zero where archives are also being removed.

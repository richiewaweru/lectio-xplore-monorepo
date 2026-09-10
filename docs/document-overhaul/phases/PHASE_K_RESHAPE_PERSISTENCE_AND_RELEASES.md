# Phase K — Reshape Persistence and Releases

## Goal
Persist new path-native artifacts cleanly while preserving useful Unit/realization/release infrastructure.

## Open these active files first
- `apps/textbook-agent/backend/src/core/database/models.py`
- `apps/textbook-agent/backend/src/infra/database/`
- `apps/textbook-agent/backend/src/application/unit_lesson/realizations.py`
- `apps/textbook-agent/backend/src/learn/authoring/builder/routes.py`
- `apps/textbook-agent/backend/src/learn/authoring/builder/service.py`
- `apps/textbook-agent/backend/src/learn/publishing/publish_validation.py`
- `apps/textbook-agent/backend/src/learn/publishing/`
- `apps/textbook-agent/backend/src/print/generation/whole_lesson/repository.py`

## Implementation tasks
- Persist Teaching Plan separately from each path realization.
- Store Print output and Learn output independently.
- Update builder source types to remove `component_lectio` and other dead legacy source types.
- Replace component-centric LearnDocument validation/persistence with node-centric validation.
- Preserve release snapshots and provenance if still useful.
- Because old lessons do not need support, use destructive schema/data cleanup where it materially simplifies the model, but only after backup and tests.

## Expected outputs
- `new persistence models/migrations as needed`
- `new Learn save/load contract`
- `updated release validation`
- `clean path realization references`

## Acceptance gate
Create fresh Learn and Print outputs, restart/reload the application, and recover both artifacts correctly from persistence with no legacy conversion.

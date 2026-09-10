# Phase A — Freeze Shared Instruction Contracts

## Goal
Make the Teaching Plan the stable, path-agnostic instructional contract and simplify learner-task meaning before any downstream rewrite.

## Open these active files first
- `apps/textbook-agent/backend/src/curriculum/teaching_plan/models.py`
- `apps/textbook-agent/backend/src/curriculum/teaching_plan/service.py`
- `apps/textbook-agent/backend/src/curriculum/teaching_plan/revisions.py`
- `apps/textbook-agent/backend/src/curriculum/teaching_plan/consumers.py`
- `apps/textbook-agent/backend/src/curriculum/teaching_plan/coverage.py`
- `apps/textbook-agent/backend/src/curriculum/teaching_plan/projections.py`
- `apps/textbook-agent/backend/src/curriculum/agents.py`
- `apps/textbook-agent/backend/src/curriculum/prompts.py`
- `packages/lectio-contracts/src/actions.ts`
- `packages/lectio-contracts/src/teaching-view.ts`
- `packages/lectio-contracts/src/index.ts`
- `packages/lectio-page/contracts/intent-catalogue.v1.json`

## Implementation tasks
- Replace/reshape `LearnerActionBrief` around the minimum semantic fields: action, target, purpose, expected_evidence, difficulty.
- Retain source/dependency information only if it is actually required for approved-item provenance; do not let it contaminate the minimal learner-task meaning.
- Keep all native identifiers out of Teaching Plan models and prompts.
- Move canonical intent ownership out of `@lectio/page`; `@lectio/contracts` or another neutral shared owner must become authoritative.
- Update teaching prompt/schema tests and coverage logic.
- Keep stable block IDs, plan identity, revision, approval and preparation hash behavior.

## Expected outputs
- `updated curriculum teaching-plan contracts and tests`
- `updated neutral intent/learner-action vocabulary`
- `recorded schema examples for passive content and learner-task blocks`

## Acceptance gate
A Teaching Plan can be generated, approved, persisted and reloaded without containing any Print form ID, Learn capability/component ID, page object ID, or interaction type.

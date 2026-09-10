# Phase N — Repository and Package Cleanup

## Goal
Make repository boundaries and scripts describe the new system instead of the architecture that was deleted.

## Open these active files first
- `package.json`
- `pnpm-workspace.yaml`
- `apps/textbook-agent/agents/project.md`
- `docs/architecture/CURRENT_SYSTEM.md`
- `docs/refactor-program/permanent/TARGET_ARCHITECTURE.md`
- `tools/xplore-program/`
- `apps/textbook-agent/tools/`
- `packages/lectio-contracts/`
- `packages/lectio-learn/`
- `packages/lectio-page/`

## Implementation tasks
- Update architecture documentation and domain guards.
- Move canonical instructional intent ownership to the neutral shared owner.
- Remove root `learn:*` package scripts if `@lectio/learn` is deleted; replace with app-level interaction/document tests where needed.
- Remove contract export/sync steps that only exist for the deleted package/component model.
- Keep `@lectio/page` scripts needed by Print.
- Keep `@lectio/contracts` only while it remains a true shared boundary; eliminate Print-owned projection direction.
- Remove stale temp/program artifacts only according to repo rules and only when clearly disposable.

## Expected outputs
- `updated `agents/project.md``
- `updated `docs/architecture/CURRENT_SYSTEM.md``
- `updated root scripts/workspace`
- `updated architecture guard rules`

## Acceptance gate
A clean checkout installs and validates without needing the deleted Learn package/component exports, and architecture guards encode the new boundaries.

# Final Acceptance Standard

The program is complete only when all are true.

## Repository shape
- Backend production code centers on `application/`, `curriculum/`, `print/`, `learn/`, `infra/`.
- No generic planning/generation/resource namespace survives without explicit justification.
- Packages are `lectio-page` and `lectio-learn`.
- Frontend follows equivalent ownership.

## Reachability
- Unit is the only supported lesson-creation path.
- Every mounted production route belongs to a supported flow.
- No obsolete studio/generation route remains mounted.
- Every production module has a known owner.

## Separation
- Print never imports Learn.
- Learn never imports Print.
- Curriculum/Infra never import realization domains.
- Final prompts, writers, validators and renderers are path-owned.
- `application/` contains orchestration only.

## Cleanliness
- Every DEAD audit item is deleted.
- No legacy-only tests preserve removed product paths.
- No obsolete exports remain.
- Temporary packs/reports are removed.
- Compatibility shims are removed or explicitly time-boxed.

## Documentation
- One current architecture description exists.
- Docs reference current paths only.
- Stale implementation packs/reports are removed after durable knowledge is retained.
- README describes the current system.

## Integration
- Unit → Print → PDF passes.
- Unit → Learn → Builder → edit/save/reload → Preview → Publish passes.
- Existing runtime/distribution/analytics integration tests pass.
- Architecture guards pass.
- DB metadata/Alembic history still loads.

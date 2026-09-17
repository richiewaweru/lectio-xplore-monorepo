# Cursor Prompt — C5: Architecture Guards + Full Integration Proof

Reread all permanent documents first. Then read cleanup state, reachability manifest, and previous report if applicable.

## Objective

Lock down and prove the cleaned architecture.

- Add backend/frontend/package import guards.
- Reject Print↔Learn imports.
- Reject Curriculum/Infra importing realization domains.
- Reject final product prompts in shared/infra.
- Reject removed legacy namespaces.
- Verify DB metadata/Alembic.
- Run @lectio/page tests/check + PDF fixture.
- Run @lectio/learn tests/build.
- Run Builder tests.
- Run Unit→Print integration.
- Run Unit→Learn→Builder→edit/save/reload→Preview→Publish integration.
- Run existing runtime/distribution/analytics integration tests.
- Produce final tree and residual list.

PASS only when all architecture and integration gates are green and remaining issues are product-quality issues rather than structural ambiguity.

## Protocol
1. Record starting SHA/branch/dirty state.
2. Inspect actual code.
3. Write a short execution plan.
4. Execute only this phase.
5. Run relevant regressions.
6. Write `docs/cleanup-program/reports/C5/PHASE_REPORT.md`.
7. Update `docs/cleanup-program/CLEANUP_STATE.md` only on PASS.
8. STOP.

If uncertain whether something is dead, reclassify it rather than guessing.

# Deferred Findings

Product bugs or integrity issues discovered during the domain refactor.

Do **not** fix these during R0–R8. Record them here and continue only if the structural move remains safe.

See also: `docs/refactor-program/permanent/KNOWN_DEFERRED_FIXES.md`.

## Findings

### R0 — `@lectio/learn` quiz evaluate test failure
- **Where:** `packages/lectio/src/test/lectio.test.ts` — “evaluates quiz answers immediately and resets with Try again”
- **Symptom:** `getByRole('button', { name: /^0\.25 m\/…})` fails; expected “Not quite!” feedback not found
- **Baseline:** 130 passed / 1 failed at SHA `a5e68a2` with no product moves
- **Action:** Fix after R8 under Learn package ownership (`packages/lectio-learn` after R6)

### R0 — Frontend Builder vitest hang (environment)
- **Where:** `apps/textbook-agent/frontend` vitest over `src/lib/builder/**`
- **Symptom:** Process starts then produces no progress for several minutes in this agent environment
- **Mitigation used:** Ran focused non-svelte frontend tests (`capabilities`, `flags`) which PASS
- **Action:** Re-verify Builder suite locally before treating R5 as green; do not “fix” by changing product behavior during moves

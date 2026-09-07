# D6 Acceptance

## D6A Print
PASS only if:
- canonical Unit fixture reaches Print generation,
- form planning/writers/assembly complete with deterministic provider fakes,
- persisted page document reloads,
- @lectio/page validation passes,
- PDF is non-empty and parseable,
- at least one recoverable-failure/retry path is asserted.

## D6B Learn
PASS only if:
- Unit reaches Learn generation,
- generated Learn document validates,
- Builder edit/save/reload works,
- Preview does not mutate release state,
- Publish creates immutable v1,
- later edit/publish creates v2 without mutating v1.

## D6C Downstream
PASS only if:
- LearnRelease can be assigned,
- assignment recipient/instance linkage is correct,
- runtime loads the intended release,
- attempts/progress persist under current semantics,
- analytics returns the tested learner/release/class data,
- cross-learner/class/release isolation is checked where feasible.

## D6D Structural
PASS only if:
- zero-legacy guard passes,
- backend domain guard passes,
- package Print/Learn guard passes,
- ORM metadata loads,
- Alembic has one valid head and upgrade sanity passes,
- @lectio/page tests/check pass,
- @lectio/learn tests/build status is recorded,
- frontend tests/typecheck/build status is recorded.

## D6E Debt/Handoff
PASS only if:
- every known debt item has ID, severity, canonical owner, dependencies, acceptance criteria, status,
- new D6 findings are added,
- Codex live-run handoff is complete.

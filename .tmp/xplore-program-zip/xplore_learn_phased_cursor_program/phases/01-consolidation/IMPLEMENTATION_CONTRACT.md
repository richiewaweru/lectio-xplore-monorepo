# Implementation Contract — Phase 01: Monorepo Consolidation + Product Boundaries

    ## Goal
    Co-locate Page, Component Lectio, and Xplore in the existing page monorepo while preserving behavior.

    ## In scope
    1. Use lectio-xplore-monorepo as permanent target.
2. Import standalone component Lectio without semantic rewrite.
3. Make Xplore consume component Lectio as a workspace dependency rather than external npm package.
4. Reconcile duplicated/diverged Xplore app/backend files using Phase 0 ownership manifest; never use latest-wins.
5. Add/strengthen dependency boundary guards: Page must not import Learn and vice versa.
6. Preserve existing Component Builder/editing/persistence and Page PDF behavior.

    ## Explicitly out of scope
    - Do not rename the component package and restructure it simultaneously if avoidable.
- Do not extract shared lesson-core yet.
- Do not build runtime/classes/analytics.
- Do not rewrite generation.

    ## Required approach

    1. Inspect the current implementation before creating or replacing anything.
    2. Apply the permanent REUSE/EXTEND/REFACTOR/REMOVE/NEW classification.
    3. Reuse current Xplore visual primitives for any UI added in this phase.
    4. Preserve unrelated dirty work.
    5. Prefer additive schema migrations and reversible changes.
    6. Add tests with behavior.
    7. Do not begin later phases.
    8. Record architecture deviations rather than silently changing the north star.

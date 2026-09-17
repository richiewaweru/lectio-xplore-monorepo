# Implementation Contract — Phase 07: Concept Evidence + Simple Progress Classification

    ## Goal
    Map runtime activity back to the existing curriculum semantics so analytics can speak in concepts and misconceptions rather than only questions.

    ## In scope
    1. Add/index Learn node→concept bindings.
2. Create attempt-concept evidence records or equivalent append-only interpreted evidence.
3. Normalize/stabilize misconception IDs where required for analytics without breaking authoring data.
4. Add learner concept-state projection.
5. Implement simple transparent Strong/Developing/Needs Practice bands using documented percentage/quantile thresholds.
6. Preserve raw evidence so classifications can later be recomputed.

    ## Explicitly out of scope
    - No sophisticated mastery probability.
- No opaque adaptive model.
- No destructive migration of existing concept cards.

    ## Required approach

    1. Inspect the current implementation before creating or replacing anything.
    2. Apply the permanent REUSE/EXTEND/REFACTOR/REMOVE/NEW classification.
    3. Reuse current Xplore visual primitives for any UI added in this phase.
    4. Preserve unrelated dirty work.
    5. Prefer additive schema migrations and reversible changes.
    6. Add tests with behavior.
    7. Do not begin later phases.
    8. Record architecture deviations rather than silently changing the north star.

# Implementation Contract — Phase 00: Baseline + Reuse Inventory + Guardrails

    ## Goal
    Establish factual current-state knowledge, golden regressions, reuse classifications, and persistent program state before implementation.

    ## In scope
    1. Inventory the target monorepo and both source lineages currently used for Page and Component Xplore.
2. Record branch/commit/dirty state and executable build/test commands.
3. Trace generation → editable Builder → persistence for Component Learn.
4. Trace Page generation → render → PDF.
5. Classify relevant systems REUSE/EXTEND/REFACTOR/REMOVE/NEW.
6. Create architecture dependency guard tests or static checks where safely possible without moving code.
7. Create persistent PROGRAM_STATE and baseline reuse manifest.

    ## Explicitly out of scope
    - No feature migration.
- No package rename.
- No DB product-feature migrations.
- No UI redesign.
- No deletion of print code yet.

    ## Required approach

    1. Inspect the current implementation before creating or replacing anything.
    2. Apply the permanent REUSE/EXTEND/REFACTOR/REMOVE/NEW classification.
    3. Reuse current Xplore visual primitives for any UI added in this phase.
    4. Preserve unrelated dirty work.
    5. Prefer additive schema migrations and reversible changes.
    6. Add tests with behavior.
    7. Do not begin later phases.
    8. Record architecture deviations rather than silently changing the north star.

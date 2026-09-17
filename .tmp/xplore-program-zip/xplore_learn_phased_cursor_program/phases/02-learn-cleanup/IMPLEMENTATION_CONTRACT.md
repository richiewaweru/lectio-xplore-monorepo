# Implementation Contract — Phase 02: Component Lectio → Web-native @lectio/learn

    ## Goal
    Sharpen Component Lectio into a web-native Learn package while preserving existing generated lesson compatibility.

    ## In scope
    1. Remove/deprecate print-only exports, contracts, metadata, CSS, registry compliance and runtime branches from component Lectio.
2. Preserve component IDs, schemas, renderers, styling and generation contracts wherever compatible.
3. Rename/package-align to @lectio/learn only after workspace behavior is green.
4. Add future-facing web metadata only where justified: interaction, response/evaluation type, narration, learner band, accessibility.
5. Keep Builder integration working.

    ## Explicitly out of scope
    - No new student runtime persistence.
- No assignment system.
- No Page editor.
- No arbitrary component redesign.

    ## Required approach

    1. Inspect the current implementation before creating or replacing anything.
    2. Apply the permanent REUSE/EXTEND/REFACTOR/REMOVE/NEW classification.
    3. Reuse current Xplore visual primitives for any UI added in this phase.
    4. Preserve unrelated dirty work.
    5. Prefer additive schema migrations and reversible changes.
    6. Add tests with behavior.
    7. Do not begin later phases.
    8. Record architecture deviations rather than silently changing the north star.

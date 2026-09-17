# Implementation Contract — Phase 04: Interactive Component Foundation

    ## Goal
    Make @lectio/learn executable through deterministic, typed interaction contracts and a compact set of reusable interactions.

    ## In scope
    1. Define common InteractionSpec, evaluation, attempt policy, hints, feedback, and completion contracts.
2. Upgrade existing suitable components such as QuizCheck and FillInBlank before creating replacements.
3. Add only missing high-value primitives: Choice/ImageChoice, MultiSelect, MatchPairs, Classify, Sequence, NumericInput/ShortResponse, ImageHotspot/DragLabel as justified.
4. Support deterministic local evaluation.
5. Establish AI-config/code-behavior rule.
6. Add accessibility/narration capability seams.

    ## Explicitly out of scope
    - No open-ended AI grading as core scoring.
- No learner DB persistence yet.
- No large simulation library.
- No arbitrary AI-generated executable UI.

    ## Required approach

    1. Inspect the current implementation before creating or replacing anything.
    2. Apply the permanent REUSE/EXTEND/REFACTOR/REMOVE/NEW classification.
    3. Reuse current Xplore visual primitives for any UI added in this phase.
    4. Preserve unrelated dirty work.
    5. Prefer additive schema migrations and reversible changes.
    6. Add tests with behavior.
    7. Do not begin later phases.
    8. Record architecture deviations rather than silently changing the north star.

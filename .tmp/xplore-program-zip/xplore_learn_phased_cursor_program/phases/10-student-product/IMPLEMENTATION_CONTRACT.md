# Implementation Contract — Phase 10: Student Home + Class + Lesson Product Flow

    ## Goal
    Complete the learner-facing product flow using the established Xplore visual language.

    ## In scope
    1. Student home: due soon, in progress, completed, classes.
2. Student class view: to do/in progress/completed.
3. Assignment launches the tabbed Learn runtime.
4. Expose own lesson progress, practice performance, graded performance, and simple concept classifications.
5. Support younger-learner visual simplification through capability/presentation, not a separate data model.
6. Ensure only own learner data is visible.

    ## Explicitly out of scope
    - No social/gamification feed.
- No complex mastery dashboard.
- No raw analytics internals.

    ## Required approach

    1. Inspect the current implementation before creating or replacing anything.
    2. Apply the permanent REUSE/EXTEND/REFACTOR/REMOVE/NEW classification.
    3. Reuse current Xplore visual primitives for any UI added in this phase.
    4. Preserve unrelated dirty work.
    5. Prefer additive schema migrations and reversible changes.
    6. Add tests with behavior.
    7. Do not begin later phases.
    8. Record architecture deviations rather than silently changing the north star.

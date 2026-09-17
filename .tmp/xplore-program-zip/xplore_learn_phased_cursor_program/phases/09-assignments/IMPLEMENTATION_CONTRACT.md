# Implementation Contract — Phase 09: Assignments + Rolling Distribution

    ## Goal
    Let teachers distribute immutable LearnReleases to whole classes, multiple classes, or selected learners with rolling enrollment semantics.

    ## In scope
    1. Add assignment definition referencing published LearnRelease only.
2. Add assignment class targets and explicit recipient rows.
3. Support selected learners and whole/multiple classes.
4. Default audience policy = rolling; retain snapshot option.
5. When learner enters an active rolling class assignment, create recipient exactly once.
6. Create/associate LearningInstance per assignment recipient.
7. Implement teacher assign UI integrated from published lesson and class pages.
8. Track assigned/started/completed/overdue/excused-ready status semantics.

    ## Explicitly out of scope
    - No assignment to mutable draft.
- No dependence on current class membership for historical recipient truth.
- No complex gradebook.

    ## Required approach

    1. Inspect the current implementation before creating or replacing anything.
    2. Apply the permanent REUSE/EXTEND/REFACTOR/REMOVE/NEW classification.
    3. Reuse current Xplore visual primitives for any UI added in this phase.
    4. Preserve unrelated dirty work.
    5. Prefer additive schema migrations and reversible changes.
    6. Add tests with behavior.
    7. Do not begin later phases.
    8. Record architecture deviations rather than silently changing the north star.

# Implementation Contract — Phase 06: Runtime Persistence + LearningInstance Execution

    ## Goal
    Create the minimum persistent learner runtime that can execute a published release, record immutable attempts, resume, and complete lessons.

    ## In scope
    1. Add learner identity model that does not require email/account.
2. Add LearningInstance as runtime context bridge.
3. Add learner sessions, immutable learner attempts, and lesson progress projection.
4. Use precise score-earned/score-possible representation.
5. Add idempotent client submission IDs.
6. Implement sequential navigation with completed-section revisit.
7. Implement V1 completion: required sections complete + required interactions attempted.
8. Keep practice and graded scoring distinct and visible.
9. Implement resume.

    ## Explicitly out of scope
    - No classes/assignments yet beyond nullable future linkage.
- No mastery algorithm.
- No repurposing aggregate marks_entries.
- No learner state in LearnDocument.

    ## Required approach

    1. Inspect the current implementation before creating or replacing anything.
    2. Apply the permanent REUSE/EXTEND/REFACTOR/REMOVE/NEW classification.
    3. Reuse current Xplore visual primitives for any UI added in this phase.
    4. Preserve unrelated dirty work.
    5. Prefer additive schema migrations and reversible changes.
    6. Add tests with behavior.
    7. Do not begin later phases.
    8. Record architecture deviations rather than silently changing the north star.

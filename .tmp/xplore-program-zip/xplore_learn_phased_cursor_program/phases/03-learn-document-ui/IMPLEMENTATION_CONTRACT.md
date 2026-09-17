# Implementation Contract — Phase 03: Learn Section Contract + Student Lesson Shell

    ## Goal
    Extend the existing LessonDocument/section model so the same generated lesson can render as a manageable student tab/stage experience without replacing Builder.

    ## In scope
    1. Inspect existing section/document types and extend rather than duplicate.
2. Add learner-facing section metadata: label, intent, required, navigation policy, completion policy where needed.
3. Add concept/evidence references at the experience-block/node seam without leaking runtime state into authored documents.
4. Introduce practice-vs-graded designation contract.
5. Build student lesson shell using existing Xplore visual system.
6. Render ordered sections as tabs/stages on desktop/tablet and compact stage navigation on phone.
7. Keep Builder as the teacher editing surface.

    ## Explicitly out of scope
    - No persistent attempts yet.
- No publishing DB yet.
- No classes.
- No new generic editor.

    ## Required approach

    1. Inspect the current implementation before creating or replacing anything.
    2. Apply the permanent REUSE/EXTEND/REFACTOR/REMOVE/NEW classification.
    3. Reuse current Xplore visual primitives for any UI added in this phase.
    4. Preserve unrelated dirty work.
    5. Prefer additive schema migrations and reversible changes.
    6. Add tests with behavior.
    7. Do not begin later phases.
    8. Record architecture deviations rather than silently changing the north star.

# Implementation Contract — Phase 05: Student Preview + Explicit Immutable Publishing

    ## Goal
    Preserve the existing generate→edit flow, add true student preview, and create immutable published LearnRelease snapshots.

    ## In scope
    1. Add teacher Student Preview that uses the actual student renderer/interaction behavior without persisting learner results.
2. Add explicit Publish action to existing lesson workflow.
3. Introduce additive LearnRelease persistence tied to exact source lesson/path lesson/revision/objective/document hash.
4. Ensure published releases are immutable.
5. Editing after publish affects draft, not published release.
6. Support v1→draft→v2 flow.
7. Reuse existing editable lesson persistence/snapshot patterns where appropriate without conflating share links with releases.

    ## Explicitly out of scope
    - No assignment system yet.
- Do not repurpose LessonShare as LearnRelease if semantics differ.
- No runtime learner history yet.

    ## Required approach

    1. Inspect the current implementation before creating or replacing anything.
    2. Apply the permanent REUSE/EXTEND/REFACTOR/REMOVE/NEW classification.
    3. Reuse current Xplore visual primitives for any UI added in this phase.
    4. Preserve unrelated dirty work.
    5. Prefer additive schema migrations and reversible changes.
    6. Add tests with behavior.
    7. Do not begin later phases.
    8. Record architecture deviations rather than silently changing the north star.

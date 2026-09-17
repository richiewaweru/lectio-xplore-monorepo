# Implementation Contract — Phase 08: Classes + Enrollment + Invitations

    ## Goal
    Create the teacher-student distribution center foundation without coupling it into Lectio Runtime.

    ## In scope
    1. Add classes.
2. Add class teacher membership with owner/teacher/assistant-ready roles.
3. Add many-to-many class learner enrollment.
4. Add invite records supporting link/code and direct invitation where existing auth supports it.
5. Support teacher-created learner without email.
6. Create teacher class UI: Overview/Students/Assignments/Progress shell, but assignments may remain placeholder until Phase 9.
7. Reuse existing app shell/design language and auth/ownership patterns.

    ## Explicitly out of scope
    - No district/SIS/guardian architecture.
- No single class_id on learner.
- No assumption each class has one teacher forever.

    ## Required approach

    1. Inspect the current implementation before creating or replacing anything.
    2. Apply the permanent REUSE/EXTEND/REFACTOR/REMOVE/NEW classification.
    3. Reuse current Xplore visual primitives for any UI added in this phase.
    4. Preserve unrelated dirty work.
    5. Prefer additive schema migrations and reversible changes.
    6. Add tests with behavior.
    7. Do not begin later phases.
    8. Record architecture deviations rather than silently changing the north star.

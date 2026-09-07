# Data Invariants

1. Published LearnRelease is immutable.
2. Assignment may only target a published LearnRelease.
3. Historical attempts remain pinned to the exact LearnRelease experienced.
4. LearnerAttempt is append-only learner truth.
5. A network retry cannot double-score the same submission.
6. Practice and graded evidence remain distinguishable.
7. Progress is rebuildable from attempts/evidence.
8. Concept state is a projection, not raw truth.
9. A learner may exist without an email/user account.
10. Student profile/teacher profile legacy tables must not be repurposed without explicit migration rationale.
11. Existing aggregate/teacher marks tables must not silently become per-learner runtime attempt tables.
12. LearningInstance uniquely represents one learner undertaking one LearnRelease in one learning context.
13. The same learner can receive the same release multiple times through separate LearningInstances.
14. Class membership is many-to-many.
15. Class teachers are membership-based, not permanently limited to one teacher column.
16. Rolling assignments preserve historical recipient timestamps.

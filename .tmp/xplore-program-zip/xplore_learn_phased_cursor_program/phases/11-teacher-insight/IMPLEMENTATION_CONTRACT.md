# Implementation Contract — Phase 11: Teacher Analytics / Insight

    ## Goal
    Expose role-specific teacher analytics derived from immutable attempts/evidence without letting dashboards become raw-table clients.

    ## In scope
    1. Create analytics service/projection APIs rather than direct frontend joins over attempt tables.
2. Class overview, lesson overview, concept overview, misconception overview, learner detail.
3. Expose completion, practice vs graded performance, first-attempt success, eventual success, attempt counts.
4. Expose simple concept classifications and common misconception prevalence.
5. Add cautious item-quality flags such as review recommended for unusually low success/high retry.
6. Use time metrics descriptively, not diagnostically.

    ## Explicitly out of scope
    - No opaque AI interpretation required for core analytics.
- No direct frontend raw attempt queries.
- No claim that time-on-task proves understanding.

    ## Required approach

    1. Inspect the current implementation before creating or replacing anything.
    2. Apply the permanent REUSE/EXTEND/REFACTOR/REMOVE/NEW classification.
    3. Reuse current Xplore visual primitives for any UI added in this phase.
    4. Preserve unrelated dirty work.
    5. Prefer additive schema migrations and reversible changes.
    6. Add tests with behavior.
    7. Do not begin later phases.
    8. Record architecture deviations rather than silently changing the north star.

# Xplore Learning Platform V2 — Full Implementation and Validation Handoff

**Repository:** `richiewaweru/text-book-generator`  
**Base branch:** `xplore`  
**Reference branch:** `v3`  
**Product focus:** Product A — teacher-facing concept paths, controlled differentiation, printable projections, and minimal response evidence.

This handoff captures the revised product direction after adversarial review of the current repository architecture and the proposed deterministic lesson-skeleton system.

## Product statement

> Map what must be learned, give each assessable capability a deliberate instructional shape, create controlled versions for different classroom needs, and produce the exact classroom resources the teacher needs.

## The new product model

```text
Topic + teaching context
        ↓
Unit scope contract
        ↓
Canonical concept path
        ↓
One assessable capability per path lesson
        ↓
Knowledge-type classification
        ↓
Deterministic lesson skeleton
        ↓
Controlled group toggles
        ↓
Existing Xplore generation, review, QC, repair
        ↓
Resource projections
        ↓
Print / marks entry / revision
```

## Hard decisions adopted

1. **Canonical concept registry is introduced now.**
2. **The path owns the objective.** Lesson generation does not rewrite it.
3. **One lesson means one independently assessable capability**, including a deliberately paired contrast when the relationship itself is the capability.
4. **Path planning is not constrained by requested lesson count or period duration.**
5. Time remains a **scheduling and feasibility layer**, not a concept-dropping planner constraint.
6. **Skeletons run in shadow mode first** and gain authority only after evaluation.
7. **Differentiation is a structural diff**, not merely a change in tone or reading level.
8. **The shared diagnostic check is locked across variants.**
9. **Resource types are projections from canonical lesson material**, not independent generations where avoidable.
10. **Continuity uses the path plan plus teacher-recorded actual outcomes**, not prior generated prose.
11. Existing Xplore invariants remain intact: item wall, pack-owned items, durable review halt, sibling isolation, teacher-edit preservation, QC recomputation.

## Recommended implementation order

```text
1. Fix current silent defects
2. Add concepts + objective ownership + provenance
3. Add skeleton preview and shadow logging
4. Run and assess 30 real lessons
5. Add units + path planner + bridge in existing UI
6. Compare path-planned vs current whole-session planning
7. Build path UI only after the gate passes
8. Add scheduling/period grouping
9. Add resource composition/projections
10. Add minimal marks-entry screen
```

## Folder map

- `00_DECISION_RECORD.md`
- `01_PRODUCT_SPEC.md`
- `02_CURRENT_SYSTEM_AND_DEFECTS.md`
- `03_DOMAIN_MODEL.md`
- `04_CONCEPT_REGISTRY.md`
- `05_PATH_PLANNER.md`
- `06_SKELETON_ENGINE.md`
- `07_DIFFERENTIATION_MODEL.md`
- `08_LESSON_BRIDGE.md`
- `09_CONTINUITY_AND_ACTUALS.md`
- `10_RESOURCE_PROJECTIONS.md`
- `11_UI_AND_FLOWS.md`
- `12_API_CONTRACTS.md`
- `13_DATABASE_AND_MIGRATIONS.md`
- `14_IMPLEMENTATION_PHASES.md`
- `15_TEST_AND_EXPERIMENT_PLAN.md`
- `16_ACCEPTANCE_WALKTHROUGH.md`
- `17_RISKS_NON_GOALS_STOP_RULES.md`
- `18_AGENT_MASTER_PROMPT.md`
- `19_AGENT_PROGRESS_TEMPLATE.md`
- `schemas/`
- `fixtures/`
- `source_material/`

## Completion standard

Do not call the redesign complete merely because the path UI exists. Completion requires:

- current silent defects fixed;
- canonical concepts and path-owned objectives;
- provenance recorded;
- skeleton shadow data collected and reviewed;
- path planning validated against the current planner;
- one path lesson prepared through the existing Xplore pipeline;
- variants expressed as inspectable structural differences;
- resource projections composed without unnecessary model calls;
- selective printing;
- minimal marks entry linked to shared diagnostic items;
- full automated and browser acceptance evidence.

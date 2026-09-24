# Ownership Migration Matrix

| Concern | Current | Target | Action |
|---|---|---|---|
| pedagogy/progression | Teaching Plan, continuity thin | curriculum/teaching_plan | strengthen |
| task semantics | shared_tasks + path interpretation | curriculum/shared_tasks | strengthen/finalize pre-fork |
| ordinary composition | shared composer called per path | SharedDocument generation | move pre-fork |
| ordinary writing | primitive-local/path calls | generic SectionWriter | replace |
| continuity | transition/neighbour handling | Teaching Plan + validator | replace |
| Learn interactions | learn | learn | keep |
| Print treatments | print | print | keep |
| page/PDF | print | print | keep |
| run state | path-specific | generic runtime | converge |
| model routing | V2/V3 capability names on current slots | truthful capability names on same slots | migrate/delete old names |
| progress | mixed DB + in-memory projection | durable run/work-item/event | converge |

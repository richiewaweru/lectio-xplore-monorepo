# Keep / Move / Delete Matrix

| Current thing | Decision | Target |
|---|---|---|
| Unit/PathLesson flow | KEEP | `curriculum/` |
| Teaching Plan revisions/approval | KEEP + simplify learner task | `curriculum/teaching_plan/` |
| Independent realization identity | KEEP | `application/unit_lesson/realizations.py` |
| dual-native helper | REVIEW / likely retire | explicit single-path admission |
| Print page engine | KEEP | `print/` + `@lectio/page` |
| Print PDF renderer | KEEP | Print only |
| Print prose/table/figure/callout knowledge | ADAPT | shared document vocabulary + Print realizer |
| Print ruled lines/response areas | KEEP | Print only |
| Print-owned intent catalogue | MOVE OWNERSHIP | neutral shared instructional owner |
| Learn `ExplanationBlock` etc. | DELETE | document primitives |
| Learn `SectionContent` component field model | DELETE | ordered LearnDocument nodes |
| Learn content capability selector | DELETE | document realizer |
| Learn `component_lectio/` ordinary lane | DELETE | new Learn generation |
| Learn strict interactions | KEEP SELECTIVELY | `learn/interactions` |
| Learn interaction writer/evaluator | KEEP SELECTIVELY | retained interactions only |
| Learn Builder save/reload/release patterns | KEEP + adapt | node-based LearnDocument |
| `@lectio/learn` general package | RETIRE if no independent consumer | app-owned document + interactions |
| `@lectio/contracts` | KEEP if neutral | canonical shared intent/action vocabulary |
| `@lectio/page` | KEEP | Print engine |
| generic Media | DELETE | none |
| video | DELETE | none for now |
| simulations | DELETE | none for now |
| old lesson compatibility | DELETE / do not build | none |
| dashboard/auth/settings | KEEP | app shell |

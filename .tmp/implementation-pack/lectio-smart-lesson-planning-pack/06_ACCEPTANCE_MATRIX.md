# Final Acceptance Matrix

The pass is accepted only when all blocking rows are green.

| Area | Requirement | Blocking |
|---|---|---:|
| Flow | Skeleton is recommendation, not exact mandatory order | Yes |
| Flow | Selected roles are from closed legal slot vocabulary | Yes |
| Flow | Objective/scope remain immutable | Yes |
| Flow | Final verification/check capability remains present | Yes |
| Flow | Cross-subject fixtures produce sensible differentiated journeys | Yes |
| Teaching | Existing Teaching Plan remains shared authority | Yes |
| Teaching | Formative response tasks can exist without approved assessment source | Yes |
| Teaching | Formal assessment still requires approved source ownership | Yes |
| Shared tasks | Every response-bearing action resolves to one SharedTaskSpec | Yes |
| Shared tasks | Print and Learn consume same SharedTaskSpec | Yes |
| Sourcebook | Concrete examples/data/facts can be bound once and reused | Yes |
| Sourcebook | Writers cannot silently contradict bound values | Yes |
| Print | No Learn-native interaction IDs leak into Print | Yes |
| Learn | No Print-native treatment/object IDs leak into Learn | Yes |
| Print | Paper response treatment preserves shared task meaning | Yes |
| Learn | Interaction preserves shared task meaning/evaluation | Yes |
| Review | Full assembled Print lesson gets coherence review | Yes |
| Review | Full assembled Learn lesson gets coherence review | Yes |
| Repair | Review produces targeted repair, not full-lesson rewrite | Yes |
| Repair | Repaired lesson is revalidated | Yes |
| Reliability | New stages use existing call budget/checkpoint discipline | Yes |
| Persistence | Sourcebook/tasks/reports are revision-bound and reloadable | Yes |
| Regression | Existing Print/Learn architecture tests remain green after intentional updates | Yes |
| Live proof | Fresh Math + History + Biology lessons generated in both paths | Yes |
| Quality inspection | No obvious internal contradiction in sampled outputs | Yes |
| Visual design | Primitive styling redesign completed | No — explicitly out of scope |

## Stop conditions

Do not declare success if:

- flow planner simply reproduces the skeleton for every fixture;
- Learn invents a task that Print does not share;
- Print drops a formative task because it lacks an approved assessment item;
- a writer can change canonical sourcebook values without failure/review;
- coherence reviewer rewrites entire lessons instead of naming repair targets;
- only one subject has been tested;
- tests pass but no fresh full output was inspected.

# Generic Section Writer

## Rule

> **Composer owns form. Writer owns expression.**

One generic writer handles any section role.

## Request

```text
section_contract:
  display_title
  entry_state
  must_establish
  avoid_repeating
  bridge_from_previous
  exit_state

composition_plan:
  exact IDs
  exact order
  exact kinds
  semantic roles
  block ownership
  task anchors

sources:
  approved facts
  sourcebook entries
  terminology
  evidence constraints

task_summaries
```

Optionally include the immediately preceding accepted final node for prose rhythm, but correctness must not depend on another writer's prose.

## Output rules

Must preserve exact shape and write learner-facing fields only.

Must establish required concepts, avoid repetition, respect entry assumptions, realize the bridge and end at exit state.

Must distribute explanatory labour across nodes rather than make every node self-contained.

Must not invent tasks/facts, expose planning language/IDs, or include path-specific instructions.

## Call budget

Recommended semantic provider budget:

```text
1 initial section generation
+ 1 section-aware repair
+ 1 narrow targeted repair
= max 3 semantic dispatches
```

Transport retry is separate and infrastructure-owned.

## Slot

Default: **STANDARD**.

## Concurrency

Parallel across sections using bounded durable work items. Initial per-lesson LLM concurrency cap: **4**.

Do not parallelize primitives inside a section.

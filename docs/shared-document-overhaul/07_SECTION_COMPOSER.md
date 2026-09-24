# Shared Section Composer

## Responsibility

Composer owns **form**, not learner-facing wording.

```text
TeachingPlanSection
+ SharedTaskSpecs
+ relevant source/visual constraints
+ closed primitive vocabulary
        ↓
SectionCompositionPlan
```

## Example

```text
section: explain
1. paragraph  bridge_and_explanation
2. figure     particle_model
3. paragraph  interpret_figure
4. task_anchor task-explain-b4
```

Each item has stable ID, kind, teaching block ownership and semantic role.

## Closed contract

Once accepted, the writer cannot add/remove/reorder/retype nodes, alter IDs or move task anchors.

## Recommended guardrails

- every block is realized;
- default one primary realization per block;
- at most two ordinary nodes for one block unless an explicit policy says otherwise;
- avoid >2 consecutive paragraphs;
- normal max one callout per section;
- Heading only for a genuine subsection;
- Figure only for visual reasoning;
- Table only for relational/tabular information;
- List only when set/sequence semantics are natural;
- every section task has a TaskAnchor;
- hard safety ceiling: 10 ordinary nodes unless explicit deterministic policy allows more.

## LLM

Use existing structured authoring stack.

Default slot: **STANDARD**.

Validate deterministically after the model. Do not accept an LLM output merely because it parsed.

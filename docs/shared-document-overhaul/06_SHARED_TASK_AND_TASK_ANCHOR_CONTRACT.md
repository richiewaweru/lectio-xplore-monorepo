# Shared Tasks and Task Anchors

## Authority

```text
TeachingPlanBlock.learner_action
        ↓
SharedTaskSpec
        ↓
TaskAnchor
        ↓
   ┌────┴────┐
 Learn      Print
 widget    treatment
```

The shared task answers what the learner does, what counts as evidence and how the response is evaluated.

## TaskAnchor

```text
id
kind = "task_anchor"
task_spec_id
teaching_block_id
role | null
```

## Writer boundary

Section Writer receives a compact task summary to prepare/stop prose appropriately, but cannot rewrite prompt/options/evaluation/action or remove/move the anchor.

## Path realization

Maintain closed mappings from shared learner action/response contract to legal Learn interaction(s) and legal Print treatment(s). A path may narrow a legal set; it may not invent new pedagogical meaning.

Unsupported mapping is a truthful failure before READY.

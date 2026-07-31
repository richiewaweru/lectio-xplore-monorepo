# Deterministic Skeleton Engine

## Source

Use versioned `skeletons.yaml` as data.

The supplied draft is copied into `source_material/skeletons-v1-draft.yaml`.

## Pipeline

```text
Approved objective
  ↓
Knowledge-type classifier
  ↓
Skeleton lookup
  ↓
Toggle expansion
  ↓
Slot plan
  ↓
Component selection within slots
  ↓
Writer fills content
```

## Shadow mode

Before authority:

```text
current StructuralPlan generation
           +
shadow skeleton preview
           ↓
comparison log
```

No output changes.

Run at least 30 real lessons spanning:

- all four knowledge types where possible;
- first exposure;
- consolidation;
- repair;
- retrieval;
- transfer;
- different subjects and grades.

## Shadow record

```python
SkeletonShadowRecord:
    generation_id
    objective
    classifier_type
    classifier_confidence
    skeleton_id
    expanded_slots[]
    current_plan_roles[]
    structural_match_score
    reviewer_preference
    deviation_needed
    notes
```

## Promotion gate

Skeleton authority is allowed only if:

- classification is acceptable;
- skeleton fit is preferred or equivalent in most reviewed cases;
- no systematic subject/grade failure;
- deviations do not exceed threshold without explanation;
- all slot/component constraints validate.

## Slot invariants

- maximum six slots;
- `check` always present;
- `check` locked;
- slot roles come from YAML;
- component choices restricted by slot;
- cognitive jobs reach component selector;
- misconception-driven confront slots max two;
- overflow produces explicit warning, never silent truncation.

## Knowledge classification

Store:

- primary type;
- optional secondary demand;
- source: model | teacher;
- confidence;
- teacher override.

## Deviation model

A deviation request includes:

```json
{
  "skeleton_id": "conceptual.first_exposure",
  "operation": "replace",
  "target_slot": "contrast",
  "replacement_slot": "model",
  "reason": "The objective requires interpreting a worked scientific model.",
  "requested_by": "model",
  "status": "pending_teacher"
}
```

## Revision rule

If a skeleton requires approved deviation in more than 20% of sufficiently sampled lessons, flag the skeleton for revision. Do not auto-change old lesson provenance.

## Compatibility

Legacy StructuralPlans continue to render. New path lessons use skeleton expansion when enabled by feature flag.

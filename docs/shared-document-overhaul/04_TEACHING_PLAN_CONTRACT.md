# Enriched Teaching Plan Contract

## Goal

Make the approved Teaching Plan sufficient for independent parallel section writers without requiring one writer to consume another writer's generated prose.

## Target plan fields

```text
learner_title
arc
starting_state[]
target_state[]
anchor_usage[]
misconception_focus_ids[]
sections[]
```

## Target section fields

```text
slot_id
display_title
specific_purpose

entry_state[]
must_establish[]
avoid_repeating[]
bridge_from_previous | null
exit_state[]

blocks[]
```

Existing block semantics remain authoritative: identity, position, intent, brief, evidence, sources, task mode, sourcebook needs/refs, stimulus dependencies and learner action.

## Meaning

`entry_state`: knowledge/skill the section may assume.

`must_establish`: what this section must make true.

`avoid_repeating`: already-established content that should not be retaught without cause.

`bridge_from_previous`: semantic relationship the section should realize naturally.

`exit_state`: state guaranteed for downstream sections if the section succeeds.

## Planner rules

The planner reasons over the whole lesson. Adjacent state transitions must be semantically compatible.

The Teaching Plan must not choose presentation primitives or native components. It may state instructional needs; the document composer decides form later.

## Approval/hash

All new pedagogically meaningful fields participate in canonical Teaching Plan content hashing.

No downstream stage may silently enrich an approved plan and claim the same revision/hash.

## Validation

Deterministic:
- required/unique identities;
- closed learner-action vocabulary;
- block/source/task invariants;
- non-empty meaningful continuity fields;
- exact section/slot ownership.

Semantic:
- whole-lesson progression coherent;
- exit state plausibly satisfies next entry state;
- target state is covered;
- unnecessary duplicated responsibility is minimized;
- tasks collect the evidence they claim to collect.

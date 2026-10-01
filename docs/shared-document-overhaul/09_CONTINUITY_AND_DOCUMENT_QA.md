# Continuity and Document QA

## Principle

Teaching Plan owns continuity.
Writer realizes it.
Validator verifies it.

No second pedagogical planner after approval.

## Section validation

Run deterministic checks first:

- exact IDs/order/kinds;
- schema validity;
- TaskAnchor completeness;
- source/fact constraints;
- no placeholders;
- no internal/planning leakage;
- primitive-specific correctness.

Then semantic checks as needed:

- all `must_establish` covered;
- `avoid_repeating` respected;
- no unsupported assumptions beyond `entry_state`;
- output plausibly reaches `exit_state`.

## Boundary work item

For adjacent A/B inspect:

```text
A.exit_state
A final few nodes
B.entry_state
B.bridge_from_previous
B first few nodes
```

Check prerequisites, repetition, abruptness, bridge realization and terminology consistency.

Boundary checks may run in parallel.

## Validator output

Only PASS or typed issue:

```text
issue_code
affected_section_id
affected_node_ids
explanation
required_correction
```

Validator does not rewrite.

## Repair

One targeted affected-section repair, then one revalidation. Still failing → recoverable failure, no loop.

## Model

Boundary semantic validation: **STANDARD**. Deterministic validation dominates.

Document semantic QA: **FAST** by default after deterministic checks; escalate only if measured quality requires it.

## Final QA

No READY until learner title/section titles, hierarchy, task coverage, continuity, required media and metadata-leak checks all pass. No final whole-lesson rewrite.

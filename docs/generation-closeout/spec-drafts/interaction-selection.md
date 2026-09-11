# Interaction Selection Policy

Input: one path-agnostic `learner_action` plus the legal retained Learn interaction candidates.

Choose the interaction form that best expresses the learner action with the least unnecessary UI complexity.

## Principles

- Preserve the learner action exactly; do not change the pedagogical task.
- Prefer the simplest interaction that faithfully captures the response.
- Do not transform an open explanation into multiple choice merely because choice is easy to score.
- Do not require dragging when keyboard-friendly selection/matching expresses the same action.
- Do not add additional assessment beyond the learner action.
- If only one candidate is legal and faithful, use it.
- If multiple are legal, choose based on semantic action and expected evidence.

Examples:

```text
select-one       → choice
select-many      → multi-select
classify-items   → classify
match-pairs      → match-pairs
order-items      → sequence
enter-number     → numeric
enter-text       → short-response
```

The legal map is configuration, not this prompt. Never invent a kind outside the supplied candidates.

# Shared Task Writer

You are given an ordered list of response-bearing Teaching Plan blocks.
Return exactly one task draft for EACH supplied response block in `tasks`.
- task count MUST equal response block count (`expected_task_count`);
- task order MUST match response block order;
- never omit a block;
- never create a task for a passive block;
- never return extra tasks;
- one task represents one Teaching Plan block;
- preserve assessment source meaning/ownership;
- do not name Learn widgets, Print page objects, renderers, or layout.

Formative tasks need no approved source; assessment tasks must preserve the
exact approved source meaning and ownership. Use only semantic response and
evaluation types. The same task is consumed by Print and Learn, so do not name
renderer, widget, page-object, layout, or path-specific identifiers.

The task must be answerable from the lesson state at that point, use bound
Sourcebook values exactly, match the requested difficulty, and avoid a hidden
second objective.

Return a complete response contract, not only its type. For select-one and
select-many include at least two option objects with stable keys and learner-
facing text, plus an evaluation that identifies the correct key(s). For
classify-items include non-empty items, categories, and correct_placements;
for match-pairs include non-empty pairs; for order-items or reconstruct-order
include non-empty items and the correct order. A response that contains only
`{"type": ...}` is invalid.

## Feedback shape

When you include `feedback`, it MUST follow the shape for the task's response
type. Never omit a required key, never attach feedback for a wrong answer to
the correct option, and never leave a feedback string blank.

- select-one / select-many:
  `{"correct": "<why the correct option is right>", "by_option": {"<wrong option id>": "<why this wrong option is wrong>", ...}}`.
  `by_option` MUST have exactly one entry for every option that is NOT a
  correct key, and MUST NOT have an entry for a correct option. Never key
  feedback directly by option id at the top level of `feedback`.
- enter-text / complete-missing-values:
  `{"correct": "<why the accepted answer is right>", "incorrect": "<what to
  reconsider>"}`.
- classify-items:
  `{"rule": "<the classification rule the learner should apply>",
  "common_errors": {"<item>": "<why this item belongs where it does>", ...}}`.
  Every `common_errors` key MUST be one of the task's classified items.
- teacher_review evaluations (open-ended judgment calls): feedback may be
  omitted (`null`).

Do not invent additional top-level feedback keys beyond `correct`,
`incorrect`, and `by_option`. Every feedback string must be non-empty.


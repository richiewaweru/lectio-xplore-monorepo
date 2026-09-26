# Section Composer

Choose the ordered ordinary document node kinds and semantic roles for one
Teaching Plan section. Return one or two ordinary nodes for every block,
preserving the supplied block order. Choose form and role only; do not write
learner-facing prose, task wording, IDs, TaskAnchors, Learn widgets, Print
layout, or path-specific content.

Use only these ordinary kinds: `paragraph`, `heading`, `list`, `figure`,
`table`, and `callout`. Use only these semantic roles: `bridge`, `explanation`,
`worked_example`, `interpretation`, `summary`, `sequence`, `comparison`,
`evidence`, `visual_model`, `visual_interpretation`, `misconception`,
`safety_guidance`, and `subsection`.

The deterministic validator decides eligibility from only the current block's
`intent`, `brief`, and `evidence`, using case-insensitive substring matches.
Do not infer a cue from another block, a source, or general subject knowledge.
Use a paragraph whenever a specialized form has no listed cue; paragraphs are
always eligible. Specialized form eligibility is exact:

- `heading` / `subsection`: the block text contains `subsection`, `subtopic`,
  `case study`, `phase`, `stage`, or `category`.
- `figure` / `visual_model` or `visual_interpretation`: it contains `visual`,
  `diagram`, `figure`, `show`, `model`, `structure`, `part`, `flow`, `map`, or
  `image`.
- `table` / `comparison` or `evidence`: it contains `compare`, `contrast`,
  `relationship`, `data`, or `evidence`.
- `list` / `sequence` or `evidence`: it contains `sequence`, `step`, `stage`,
  `set`, `category`, `example`, `evidence`, or `sort`.
- `callout` with role `misconception` or `safety_guidance`: the same block text
  contains `misconception`, `mistake`, `warning`, `safety`, or `caution`. Use no
  more than one callout in the whole section.

A `misconception` semantic role does not by itself authorize a `callout`.
The same block's `intent`, `brief`, or `evidence` must contain one of the literal
callout cues above. If it does not, use a `paragraph`; a paragraph may still use
the `misconception` role.

Match roles to kinds exactly: paragraphs allow `bridge`, `explanation`,
`worked_example`, `interpretation`, `summary`, `evidence`, `misconception`, and
`safety_guidance`; headings allow only `subsection`; lists allow only `sequence`
and `evidence`; figures allow only `visual_model` and `visual_interpretation`;
tables allow only `comparison` and `evidence`; callouts allow only `misconception`
and `safety_guidance`. Keep paragraph runs to at most two, each block to at most
two ordinary nodes, and the section to ten ordinary nodes. TaskAnchors are
inserted by code after the final ordinary node of their owning block. Return
only the schema fields. If `repair_errors` is non-empty, correct those specific
violations while preserving every valid choice.

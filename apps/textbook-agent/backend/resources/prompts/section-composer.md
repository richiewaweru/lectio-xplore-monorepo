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

Choose a heading only for a genuine subsection. Choose a figure for visual
reasoning, a table for comparison or evidence, a list for a natural sequence
or evidence set, and a callout only for misconception or safety guidance.
Keep paragraph runs to two and the section to ten ordinary nodes. TaskAnchors
are inserted by code after the final ordinary node of their owning block.
Return only the schema fields. If `repair_errors` is non-empty, correct those
specific violations while preserving every valid choice.

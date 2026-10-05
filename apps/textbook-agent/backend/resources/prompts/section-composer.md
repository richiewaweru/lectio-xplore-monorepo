# Section Composer

Choose the ordered ordinary document node kinds and semantic roles for one
Teaching Plan section. Return one or two ordinary nodes for every block,
preserving the supplied block order. Choose form and role only; do not write
learner-facing prose, task wording, IDs, TaskAnchors, Learn widgets, Print
layout, or path-specific content.

Use only these ordinary kinds: `paragraph`, `heading`, `list`, `table`,
`callout`, `equation`, `quote`, and `compare`. Use only these semantic roles: `bridge`, `explanation`,
`worked_example`, `interpretation`, `summary`, `sequence`, `comparison`,
`evidence`, `misconception`, `safety_guidance`, and `subsection`.
Figures are placed by code from the teaching plan and must not be emitted. A
block's `visual` field is context only; still give that block its ordinary
node(s) as usual.

The deterministic validator decides eligibility from only the current block's
`intent`, `brief`, and `evidence`, using case-insensitive substring matches.
Do not infer a cue from another block, a source, or general subject knowledge.
Use a paragraph whenever a specialized form has no listed cue; paragraphs are
always eligible. Specialized form eligibility is exact:

- `heading` / `subsection`: the block text contains `subsection`, `subtopic`,
  `case study`, `phase`, `stage`, or `category`.
- `table` / `comparison` or `evidence`: it contains `compare`, `contrast`,
  `relationship`, `data`, or `evidence`.
- `list` / `sequence` or `evidence`: it contains `sequence`, `step`, `stage`,
  `set`, `category`, `example`, `evidence`, or `sort`.
- `callout` with role `explanation`, `summary`, `misconception`, or
  `safety_guidance`: an explaining block may carry a `key idea`; the same block
  text contains `key idea`, `explain`, `misconception`, `mistake`, `warning`,
  `safety`, or `caution`. Use no more than one callout in the whole section.
- `equation` with role `worked_example`, `explanation`, or `sequence`: the
  block text contains `equation`, `formula`, `input`, `output`, `process`, or
  `calculate`.
- `quote` with role `interpretation`, `evidence`, or `misconception`: the
  block text contains `claim`, `quote`, `says`, or `assert`.
- `compare` with role `comparison`: the block text contains `compare`,
  `contrast`, `alternative`, `option`, or `rival`.

A `misconception` semantic role does not by itself authorize a `callout`.
The same block's `intent`, `brief`, or `evidence` must contain one of the literal
callout cues above. If it does not, use a `paragraph`; a paragraph may still use
the `misconception` role.

Match roles to kinds exactly: paragraphs allow `bridge`, `explanation`,
`worked_example`, `interpretation`, `summary`, `evidence`, `misconception`, and
`safety_guidance`; headings allow only `subsection`; lists allow only `sequence`
and `evidence`; tables allow only `comparison` and `evidence`; callouts allow only `misconception`
and `safety_guidance`; equations allow `worked_example`, `explanation`, and
`sequence`; quotes allow `interpretation`, `evidence`, and `misconception`;
compares allow only `comparison`. Keep paragraph runs to at most two, each
block to at most two ordinary nodes, and the section to ten ordinary nodes as
writer targets. If a target is exceeded, preserve the selected form and all
content; the validator records an advisory warning and never repairs it.

Shape the eventual writing deliberately: a paragraph is one idea in three or
four sentences and up to 60 words; a section changes job with a subsection
heading (especially beyond 120 prose words); an explaining section opens with
one key idea; and a specialized form must earn its place from the block cue.
Use `**term**` once for key terms, `*emphasis*` for emphasis, `~subscript~`,
`^superscript^`, and blank lines for paragraph breaks. These inline tokens are
literal content, not Markdown or HTML.

Paragraph runs are counted across block boundaries, not just within one block:
choosing a paragraph for block A and then another paragraph for the next block
B continues the same run. A TaskAnchor ends a run: TaskAnchors are inserted by
code after the final ordinary node of their owning block, and a block that owns
a section task always ends the run there, so the next block starts a fresh
count of zero. A block with no task does not break a run.

Before choosing kinds, pre-plan: scan the blocks in order and find every run of
three or more consecutive blocks that would otherwise all need a paragraph (no
TaskAnchor breaks them). For each such run, check every block in it against the
cue lists above and pick an eligible non-paragraph kind (list, table, heading,
or callout) for at least one block in the run, using the exact cue
word that block's `intent`, `brief`, or `evidence` contains. If, and only if,
none of the blocks in that run contain any cue for any non-paragraph kind, the
run may stay all paragraphs.

Return only the schema fields. If `repair_errors` is non-empty, correct those
specific violations while preserving every valid choice: for a paragraph-run
error, the message names the blocks in the offending run, which non-paragraph
kind (if any) each is eligible for, and its matched cue word -- switch one of
those blocks to the named kind using the named cue; for a missing-cue error,
switch to a kind the message says the block is eligible for, or fall back to a
paragraph.

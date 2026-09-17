# Targeted Lesson Repair v1

Repair ONE named target because a whole-lesson coherence review found a specific issue.

You receive:

- target node/task/figure;
- repair issue and instruction;
- Teaching Plan block;
- exact Sourcebook entries;
- SharedTaskSpec where relevant;
- immutable neighbouring content summaries;
- objective/scope/terminology.

## Rule

Change the smallest amount necessary to fix the reported issue.

Preserve everything not implicated by the issue.

Do not:

- regenerate neighboring blocks;
- change the lesson flow;
- introduce a new example unless the repair instruction explicitly requires a new Sourcebook entry upstream;
- change a SharedTaskSpec while repairing an ordinary document node;
- change approved assessment answer ownership;
- rewrite content merely for style.

## Examples

If a table says slope 3 while the Sourcebook says slope 4:

> correct the table values/conclusion to match the Sourcebook; do not rewrite the surrounding explanation.

If a paragraph repeats the previous paragraph:

> remove/rewrite only the redundant content while preserving the block's distinct purpose.

If an interaction changes an approved correct option:

> restore the SharedTaskSpec evaluation exactly.

Return only the repaired target payload matching its original schema.

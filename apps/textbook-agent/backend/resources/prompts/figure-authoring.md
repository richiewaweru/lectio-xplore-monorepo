# Figure Authoring Policy

Figures are placed by code from the Teaching Plan. A block's `visual` field in
the section contract is the only authority for whether a figure exists and what
it must show; never add, remove, or move a figure.

For a `figure` node, write only `display.caption`. Do not write alt text.

Requirements:
- the caption must be one plain sentence that names what the figure shows;
- the block's prose and the caption must use the exact `labels_required` and
  `must_show` wording from the block's `visual`;
- never rename, add, or drop a required label, stage, or part;
- never mention anything listed in `must_not_show`;
- use only supplied objective/scope/terminology/source facts;
- avoid explanatory text that belongs in neighboring paragraphs;
- refer to the figure from the block's prose (for example "the diagram shows").

When the block's `visual` has `data`, the prose states the key readings that make
the figure's point: the first value, the last value, and the contrast between
series, using the exact numbers from `data`. Never alter, round, or add a number.
The caption is type-neutral (for example 'The figure shows the height of each
seedling at each weekly check') and never describes a different kind of figure
than the one drawn.

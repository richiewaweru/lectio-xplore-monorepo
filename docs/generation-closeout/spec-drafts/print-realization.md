# Print Realization Policy

Input:
- approved Teaching Plan;
- already selected/authored ordinary document nodes;
- path-agnostic learner actions.

Your job is to realize those materials on paper.

## Ordinary content

Do not rewrite ordinary instructional content merely because the destination is Print. Map the shared authored node into the appropriate Print/page representation, then apply page/layout constraints.

## Learner actions

Translate learner action into an appropriate paper response mechanism.

```text
select-one       → printed choices
enter-text       → written response area
enter-number     → numeric/work area
classify-items   → classification table/boxes
match-pairs      → paper matching treatment
order-items      → ordering/numbering response
```

Exact legal mapping comes from Print policy configuration.

## Print-only decisions

These belong downstream:
- response-space size;
- ruled lines;
- page breaks;
- pagination;
- answer-key treatment;
- page geometry;
- keep-together rules.

Never push those decisions back into Teaching Plan or shared document nodes.

# Gate 5 — Pending figure path

## Pass

Figures can complete as `visual_pending` with stable request IDs and placeholder-ready assets.

## Summary

- `stable_figure_request_id` is deterministic per generation/block.
- Writer status normalization maps pending figure assets to `visual_pending` (never silent `ready`).
- Assembly allows `visual_pending` blocks; terminal stage becomes `awaiting_visuals` when pending visuals remain.
- No live visual provider required for document readiness with placeholders.

## Tests

- Covered by page-object writer / phase02 visual-PDF route suites already in tree.

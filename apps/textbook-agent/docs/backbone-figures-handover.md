# Backbone figures: planning to media handover

Status: planning side done on `feat/backbone-figures-reuse`; media side not started.
Line numbers below are for this branch's `document/` and `media/` (under `backend/src`).

## Purpose
A lesson backbone pins one anchor scenario with exact data and a set of figure specs.
The approved questions are written against those figures (for example "a rectangle
9 m by 4 m"). The figure the learner sees must therefore carry exactly the backbone's
numbers. Planning now guarantees which block owns which figure; media must draw it
from the backbone data instead of re-deriving numbers from prose.

## What planning now provides
- `VisualSpec.figure_ref: str | None` (`curriculum/teaching_plan/models.py`). The
  backbone figure id the block's visual draws. Omitted from dumps and hashes when
  `None`, so existing plans and content hashes are unchanged. Setting it changes the
  plan content hash, so it is already pinned by `source_plan_hash`.
- `BackboneFigure` (`curriculum/backbone/models.py`): `id`, `purpose`, `must_show`,
  `labels_required`, `data` (exact numbers/coordinates, free-form dict), `mode`
  (`diagram` | `image` | `None`, read it through `effective_mode`).
- `packet.backbone` (`LessonBackbone` dump including `figures`) and
  `packet.item_backbone_refs` (`{approved_item_id: {target, figure_id}}`) on the
  teaching packet.
- Guarantee (hard validation `FIGURE_REF_MISSING` / `FIGURE_REF_UNKNOWN`, plus a
  deterministic repair `_repair_missing_figure_visuals` in
  `application/unit_lesson/teaching_planner.py`): every approved question whose
  backbone ref has a `figure_id` is owned by a block whose `visual.figure_ref` equals
  that id, and the visual's mode, purpose, must_show and labels are copied from the
  backbone figure. The composer places a block's figure immediately before that
  block's task anchors (`document/shared_lesson/composer.py` ~579-592), so the figure
  appears right before the question that needs it. Teaching blocks may also carry a
  backbone figure (for example the worked example on the anchor's figure).

## Current gap
Nothing in `document/` or `media/` reads the backbone or `figure_ref`.
- `_figure_order_from` (`document/shared_lesson/media.py` 485-543) builds the work
  order only from the free-text `VisualSpec` plus caption and referring sentences.
- `media/render/spec_builder.py` (`_request_block`, line 78) hands those texts to an
  LLM which re-derives the numbers. It can disagree with the backbone data.
- `TeachingPlanSource` (`document/shared_lesson/runtime.py` 96) carries the plan, not
  the backbone, so the backbone is not reachable where work orders are built.

## Proposed change
1. Thread the backbone to media: add an optional `backbone_figures: dict[str, dict]`
   (id to `BackboneFigure` dump) to `TeachingPlanSource` (`runtime.py` 96), populated
   where the source is loaded from the packet, and pass it from
   `media_dispatcher.py` 181-186 (`build_figure_work_order`) and from
   `_plan_visual_spec` (`media_runtime.py` 285-299) into the rebuild.
2. `_figure_order_from` (`media.py` 485): when `spec.figure_ref` resolves in the
   backbone, take the figure's `data` as authoritative. Add `figure_id: str | None`
   and `figure_data: dict | None` to `VisualGeneratorWorkOrder`
   (`media/generation/contracts.py` 122-133, defaults `None`, so existing orders stay
   valid).
3. Include `figure_ref` and a canonical hash of `figure_data` in
   `figure_semantic_hash` (`media.py` 381-405), only when set, so hashes of existing
   figures do not change.
4. `rebuild_figure_work_order` (`media.py` 584-630) rebuilds the spec from the frozen
   order when no plan spec is given; it must also preserve `figure_ref` and the figure
   data, otherwise the equality and hash check in `media_runtime.py` ~310-335 fails for
   backbone figures.
5. `media/render/spec_builder.py` `_request_block` (line 78): render `figure_data` as
   authoritative ("use these values exactly; do not change or add numbers"). Better,
   bypass the LLM when the data already matches a family spec (for example polygon
   points or dimensions for `polygon_area`) and build the typed spec directly.
6. `mode: image` already routes to the image provider via
   `document/shared_lesson/figure_executor_adapter.py`; no routing change needed.

## Open questions
- Single-figure retry: does regenerating one figure keep `figure_ref` and data via
  the frozen order, and does the plan hash change if the backbone is regenerated
  without re-planning?
- Image QA: should image-mode figures be checked against `must_show` (and labels)
  from the backbone figure after generation?
- Image figures with `data`: should numbers be injected into the image prompt, or is
  the data only meaningful for diagram mode?
- Backbone persistence: confirm the backbone is stored with the approved plan so the
  media stage can load it without recomputing the packet.

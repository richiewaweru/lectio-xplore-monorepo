# Code-rendered figures (`media/render`)

Status: built on `feat/render-figures`, behind `LECTIO_RENDER_FIGURES` (default `off`).

## Why
Image models draw what looks plausible, not exact geometry. The L-shaped-floor lesson
shipped figures with rectangle B on the wrong side, a duplicate "5 m", and the alcove
in the wrong corner. For figures that are really data (shapes with dimensions,
number lines, charts, graphs, flows, cycles), code now draws them exactly.

## The three figure modes
| Mode | Who draws | Labels | Use for |
|---|---|---|---|
| render (via `diagram` + auto-routing) | Python/matplotlib from a typed spec | Placed exactly; lengths measured from geometry | Maths, charts, graphs, flows, cycles |
| `diagram` | Image model, schematic style | Model-drawn today (see follow-ups) | Named parts: biology, apparatus |
| `image` | Image model, illustration style | None or few | Scenes, realism |

Facts confirmed in code: `diagram` and `image` both go to image models; the label
compositor (`media/diagram_compositor.py`) adds a key band under the image and never
runs in the shared-lesson path (`visual_style` is not set there).

## Ownership
- **Planner:** unchanged. It may later add `mode: "render"` / a free-form `render_type`
  hint (never rejected); media already resolves families without it.
- **Media:** owns family choice, spec building, validation, repair and drawing.
  The 8-minute planner call is never re-run for a figure problem.

## Pipeline
```
VisualGeneratorWorkOrder (purpose, must_show, labels, caption + referring sentences + facts)
  -> RoutingFigureExecutor (document/shared_lesson/figure_executor_adapter.py)
       flag off, or mode != "diagram"  -> existing image path, unchanged
  -> render_figure (media/render/pipeline.py)
       spec builder (FAST node v3_figure_spec): family | "none" + spec JSON
       validate_spec: structural maths checks
       invalid -> repair call with exact errors (max 2)
       render_spec -> SVG (text as outlines) + PNG
       cross_check_numbers: computed values must appear in the lesson text (soft)
```

## Outcomes and policy
| Situation | Result |
|---|---|
| No family fits / builder call fails | `Fallback` -> existing image path; `render_family_fallback` log event (hint, purpose) |
| Family chosen, still invalid after 2 repairs | `Unavailable` -> failed block (`render_spec_invalid`); never an image |
| Labels cannot fit legibly | `Unavailable` (`render_layout_failed`) |
| Rendered, a number not found in text | `ready_with_quality_warning` with `qc_reasons` |
| Rendered cleanly | `ready` |

Teacher-facing policy: figures ship with flags; teachers fix them. No automatic image
regeneration.

## v1 families (`media/render/families/`)
Families are kinds of drawing; the spec's data is the figure (the L-room is
`polygon_area` with six points; there is no `l_shape` type).
- `polygon_area`: any straight-edged shape by corner points; edge labels `computed`
  (whole or 1 dp), `symbol` (x, ?) or `hidden`; split/height segments with right-angle
  marks; shaded regions. Figure series reuse the same points.
- `number_line`: integer/decimal/fraction ticks, points (open/closed), jumps, intervals.
- `bar_chart`: single or grouped (≤ 3 series, ≤ 12 categories), vertical/horizontal.
- `function_graph`: structured curves only (`linear`, `quadratic`, `polyline`), points.
- `flow`: ≤ 8 nodes, step/decision/terminal, deterministic layered layout, back-edges.
- `cycle`: 3–8 stages round a circle, optional centre label.

Each module exposes `validate`, `draw`, `describe` (alt text), `numbers`, `GALLERY`.

## Quality guarantees
- House style in `media/render/style.py`; text exported as outlines (`svg.fonttype=path`),
  fixed SVG hash salt and no dates, so the same spec gives identical bytes.
- Labels are checked against each other and against drawn lines (`media/render/layout.py`).
- Review gallery: `uv run python scripts/render_gallery.py` -> `outputs/render_gallery/index.html`
  (19 reference figures, all eyeballed). Tests: `tests/media/test_render_*.py`,
  `tests/document/test_render_routing_executor.py`.

## Turning it on
Set `LECTIO_RENDER_FIGURES=auto` on the backend. Resolve the two open items below first.

## Open items (found while wiring)
1. **A failed required figure blocks the lesson.** `bind_generated_figure` raises for a
   failed block (`document/shared_lesson/media.py:566`), and the post-section pipeline
   returns `blocked` when required media failed (`post_section_pipeline.py:334`). The
   agreed policy is "ship the rest, flag the figure". Until that exists, an `Unavailable`
   render blocks a lesson that an inexact image would previously have let through.
   Decide before enabling `auto`: either build "figure unavailable" shipping, or
   temporarily route `Unavailable` to the image path.
2. **Print with SVG is unverified.** Learn renders `<img src>` (`frontend/src/lib/learn/document/renderers/FigureNode.svelte:26`), so SVG works there.
   Print passes `media.asset_url` straight through (`print/generation/shared_document_adapter.py:119`).
   Chromium should keep it vector, but this has not been checked end to end. If it fails,
   bind the PNG (`fallback_image_url`) for print.

## Follow-ups (separate work orders)
- Numbered labels for `diagram` mode: digits drawn by the model, words in a code key band;
  turn the compositor on in the shared path; digit-count QC.
- Teacher edit for rendered figures ("move the notch to the top-right" -> spec update -> redraw).
- Teacher view of flagged figures (QC reasons, render warnings).
- Figure numbering at document assembly (every figure is currently "Figure 1").
- v2 families driven by fallback telemetry (`circle_parts` first); a general geometry
  canvas only after that.

## Note for the planning chat
Optional, small: add `"render"` to `VisualSpecMode` and a free-form `render_type: str | None`
to `VisualSpec` (`curriculum/teaching_plan/models.py`). Never reject unknown values. Media
treats it as a hint; until then, media auto-routes `diagram` figures.

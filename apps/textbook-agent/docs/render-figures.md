# Code-rendered figures (`media/render`)

Status: on by default (`LECTIO_RENDER_FIGURES=auto`); set it to `off` as a kill switch.

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
| Family chosen, still invalid after 2 repairs | `Unavailable` -> failed attempt (`render_spec_invalid`); never an image. After the work item's 3 attempts the figure ships as unavailable (see below) |
| Labels cannot fit legibly | Same, with `render_layout_failed` |
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
`LECTIO_RENDER_FIGURES` = `auto` (default) | `off` (kill switch: every figure takes the
image path). Tests default it to `off` in `tests/conftest.py` and opt in explicitly.

End-to-end check (2026-10-06, local, Grade 6 "Area of compound shapes"):
- 6 figures, all ready on attempt 1. 3 were code-rendered (`polygon_area`, served as
  `image/svg+xml`); 3 fell back to the image provider with numbered labels and a key band.
- Learn showed "Figure 1." to "Figure 6." in order. Print exported a 13-page PDF with
  continuous numbering, and the lesson reached READY.
- Seen during that run and fixed here: captions said "on square grid paper" but the code
  figures had no grid (`polygon_area` now has `grid`). Fallback telemetry fields were also
  missing, because the JSON log allowlist dropped them (`infra/logging.py`).
- Known limits:
  - Chromium embeds the SVG as a high-resolution raster in the PDF; it is sharp but not vector.
  - The unavailable-figure placeholder was not hit in this run; tests cover it.
  - The Learn caption text looked faint in a headless screenshot (unconfirmed).
  - Older drivers (`run_whole_lesson_proof.py`, `live_treasure_joe_d_unit_learn.py`) still call
    the removed `/api/v1/v3/chunked/{id}/approve` route.

## Unavailable figures ship (all modes)
Decided 2026-10-06 for render, diagram and image figures alike.
- When a figure's media exhausts its retries (3 work-item attempts), or fails with a
  non-retryable provider code (HTTP 400/401/403/404), `media_runtime` completes the media
  WorkItem with a durable `UnavailableFigureMediaResult`: the same verified identity as a
  ready result, no asset, a teacher-safe `reason` and the attempt count
  (`document/shared_lesson/media.py`).
- Every checkpoint (document QA, handoff, finalizer, promote, realization) accepts it.
  QA emits `figure_media_unavailable` as **advisory** (flagged in both gate modes).
- A declared figure with **no** media result stays a hard `required_media_missing`.
  That points to a pipeline bug. Integrity/checkpoint failures also stay hard.
- Learn shows a "Figure couldn't be generated" placeholder with the reason. Print emits
  `asset.status = "failed"`, which shows the existing "Figure unavailable" placeholder.
  Issue projection and lesson progress report the figure as unavailable (warning).

## Numbered labels for diagram figures
Diagram-mode figures that reach the image path (including render fallbacks) use
`visual_style = "diagram_numbered"` for every provider:
- the model draws only the digits 1..N on the named parts;
- `diagram_compositor` appends a key band ("1 Petal", "2 Stamen", ...);
- visual QC checks each digit appears exactly once and no words appear.
Work orders admitted before this change (no style) still verify on resume.

## Figure numbering
Figures are numbered 1..N across the whole lesson in Learn (`figureOffset` per section
canvas) and Print (`SectionView` seeded per section). Before, each section restarted at 1.

## Next work order: retry a single figure (deferred)
Not minimal, because a shipped lesson's Run is terminal. What it needs:
1. A reopen transition (`ready` -> `running`, stage media) in
   `infra/generation_runtime/repository.py`, plus the Run-status guards widened at
   `media_runtime.py` (admit_repaired ~487), `repository.py` (~1871, ~1913) and
   `post_section_pipeline.py` (~153).
2. A `regeneration_nonce` in the figure composition identity, so the replacement passes the
   changed-identity guard (`repository.py` ~1876) and gets a fresh attempt budget.
3. A route `POST /runs/{run_id}/figures/{figure_node_id}/regenerate`. It rebuilds the order
   from the active leaf (`work_order_from_composition_identity`), admits the replacement
   and reopens the Run.
4. A document-QA and finalize re-run path that takes the existing document plus the new
   media and writes a new document revision. The review-leaf path assumes an edited draft.
Until then, teachers use the whole-lesson Regenerate.

## Remaining follow-ups
- Teacher edit for rendered figures ("move the notch to the top-right" -> spec update -> redraw).
- v2 render families driven by `render_family_fallback` telemetry (`circle_parts` first).

## Note for the planning chat
Optional, small: add `"render"` to `VisualSpecMode` and a free-form `render_type: str | None`
to `VisualSpec` (`curriculum/teaching_plan/models.py`). Never reject unknown values. Media
treats it as a hint; until then, media auto-routes `diagram` figures.

# Figure representation — eval findings (2026-10-09)

Probe set: `probes.json` (12 probes). Harness: `scripts/eval_figure_prompts.py`.
Contact sheets (git-ignored): `out/figeval/{baseline,after,after-all-labelled,baseline-image,baseline-render}/index.html`.

In production a `mode: diagram` figure tries the code renderer first. Gemini only draws it
when the renderer returns `none`. On this probe set that happens for the sunflower/hamster
comparison, the flower parts, the leaf process and the conductors table.

## Diagram path (Gemini)

| Probe | Baseline (numbered) | After (A1–A3) | Every diagram drawn with Gemini labels |
|---|---|---|---|
| sunflower-hamster (comparison) | Values scattered, digits repeated, data only in the key | **Clean comparison table, exact values** | same as After |
| heart-rate (bar data) | Digits 5 and 6 printed on the y-axis, which misreads the scale | **Correct labelled bars** | same |
| bean height (change over time) | numbered | **Correct bar chart** | same |
| flower parts | Words leak in, "Petal" points at a stamen, digit 1 missing | still numbered (labels have no digits) | **Clean, every label correct** |
| frog cycle | Digit 2 drawn twice, words leak in | still numbered | **Clean** |
| leaf process | Made-up formula "C₂+Cl₂₃", digit 3 missing | still numbered | Readable, but "carbon dioxide" appears 3× and "food" 2× |
| conductors table | Yes/No turned into the digits 6 and 7, unreadable without the key | still numbered | **Clean table** |
| number line, L-shape, timeline | numbered | Correct and labelled | same |

**Decision (2026-10-09).** When Gemini is the provider, `execute_visual` now runs every
`diagram_numbered` order as a diagram where Gemini draws the labels itself. Other providers keep
numbered mode. Final run: `out/figeval/final`, and side by side with the baseline in
`out/figeval/compare/index.html`. All 12 probes came out clean, except that the leaf process
still duplicates some labels (`oxygen`, `sugar`) and has one oxygen arrow pointing the wrong
way. Busy process figures are the next thing to tune.

**Why.** The A1 rule fixes data figures. But numbered mode is unreliable on Gemini for
every kind of diagram: Gemini ignores the digits-only instruction and puts digits on the wrong
parts. The remaining weakness of Gemini-drawn labels is an occasional duplicated label
(leaf). Visual QC is off, so nothing catches that today.

## Code render path (Phase B)
- bar_chart, flow, cycle, number_line and polygon_area render exact values cleanly. No change needed.
- Gap: there is no table family, so tables and comparisons return `none` and fall through to
  Gemini. Gemini now draws them well (above), so a table family is optional, not urgent.

## Image path (Phase B)
- Filtration apparatus: clean and correctly labelled.
- Pond food chain: readable but loose, with stray lines and an unclear chain order.
- Possible tune: a light version of the representation block for image mode (for example,
  "make the relationship in PURPOSE visible: order and arrows"). Hold until we have more scene samples.

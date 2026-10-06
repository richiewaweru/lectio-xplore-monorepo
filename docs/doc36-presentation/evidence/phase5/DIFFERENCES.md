# Phase 5 — Differences from the five canvas artboards

Compared by reading the PNGs in `../track-a/reference/` against:
Learn: `learn/phase5-photosynthesis-learn-1280.png` and `-390.png` (plus the golden and legacy captures).
Print: `pdf/images/phase5-photosynthesis-print-student-1..6.png`, teacher `pdf/images/phase5-photosynthesis-print-bg-on-7..8.png`, greyscale in `pdf/images/gray/`.

Pre-accepted by the lead (not repeated below): Fraunces instead of Newsreader; Print carries the full shared wording so more pages; no subject/lesson-number eyebrow (data absent); page breaks differ; the golden m^2^ note is fixture-only; the figure lacks reference labels (doc 35).

Important context: the generated lesson never reached READY (required figure failed with image-provider HTTP 401, see `PHASE5.md`). Captures are of the text-only draft the pipeline itself assembled, shown through the dev fixture route (Learn) and the page fixture route (Print), with a neutral placeholder image in Print only. The lesson did not choose an equation, table, compare, quote, ordered list, subheading or sub/superscript, so those artboard elements cannot be compared on fresh output. They were verified on the golden fixture by Tracks A and B.

## Learn (artboard 6ceffc7b)

| # | Difference | Mark | Reason |
|---|---|---|---|
| L1 | Title wraps to three lines (artboard: two) | acceptable | The generated title is longer ("How a plant makes its own food: light, water and air in the leaves"). |
| L2 | Lesson map renders as wrapping cards (artboard: one row of small pills); in the card for section 2 the word "photosynthesis" touches the card edge | **fixed** `6f2ae8b9`, `59f825e9` | Map items now sit in an auto-fit grid (minimum 190px), the label wraps inside the padding and never breaks mid-word unless it cannot fit. Evidence: `fixes/learn/lesson-map-1280.png`, `lesson-map-390.png`, DOM metrics in `fixes/learn/fixes.log` (no horizontal scroll at 390). |
| L3 | No subheadings, no ordered list, no equation, table or compare in the lesson | acceptable | Content choice. Writer advisory `shape_missing: section/subheading` was raised and not acted on, as doc 36 2.5 requires. |
| L4 | No figure (artboard has a pot illustration) | acceptable | Doc 35 territory. Provider returned 401. Learn renders nothing for a missing asset (A7). |
| L5 | Misconception cards show the writer's title ("The soil account") where the artboard shows "COMMON BELIEF 1"; no cross / tick marks beside "The belief" and "So" | acceptable | The label is the writer's own title text. The cross and tick are not in doc 36 section 2.1 and are absent from the golden fixture too. Cheap polish if the owner wants it. |
| L6 | Task header right-hand text is "PRACTICE" or "CHECK - CHOOSE ONE" (artboard "PREDICTION - NOT MARKED" or "CHECK - CHOOSE ONE") | acceptable | Mode text derives from the task role. This lesson has no predict task. The golden fixture shows "PREDICTION - NOT MARKED". |
| L7 | Primary button is salmon and faded before a choice is made (artboard shows full-strength orange) | acceptable | Disabled state until an answer exists. Enabled state is shown in `learn/phase5-q5-right-feedback.png`. |
| L8 | The correct-answer feedback has no leading check icon | **fixed** `59f825e9` | Correct feedback now leads with an inline SVG check (#1B5E40 disc, white tick) on the #E4F0E8 panel; incorrect and saved feedback have no icon. Evidence: `fixes/learn/phase5-q5-right-feedback.png`, `fixes/learn/match-pairs-feedback.png`. |
| L9 | Unordered list had no bullet markers in Learn (Tailwind preflight reset) | **fixed** `2a5e189a` | Bullets now render (`list-style: disc`). Print already had bullets. Evidence: `learn/phase5-photosynthesis-learn-1280.png` is the post-fix capture. |
| L10 | Match-pairs task renders two columns of buttons that carry no `aria-pressed` (selected state is a CSS class only) | **fixed** `59f825e9` | Match items are native buttons with `aria-pressed` (left: selected or matched; right: matched). Evidence: `fixes/learn/fixes.log` (before/after states), `fixes/learn/match-pairs-left-selected.png`, `match-pairs-all-matched.png`. |

## Print (artboards 2352c12b, c7001af4, 729a9f1d, 03f8091c)

| # | Difference | Mark | Reason |
|---|---|---|---|
| P1 | Page 1 holds title, Name, Date and a Contents list, then section 1 starts on page 2 (artboard: section 1 starts under the title) | acceptable | Contents list is allowed with five sections (B1). Page breaks differ (pre-accepted). Page 1 is left about 55% empty, which looks unfinished. |
| P2 | Name and Date are stacked lines under the title (artboard: on the title row) | acceptable | Layout choice; both lines present. |
| P3 | Key idea box is white with a 1px border (artboard: green tint) | **fixed** `14370a01` | Key idea prints with #E4F0E8, a 1px #1B5E40 border, 18pt bold and `print-color-adjust: exact`. Tint survives background graphics off. Evidence: `fixes/pdf/images/phase5-photosynthesis-print-student-2.png` (colour), `fixes/pdf/images/gray/phase5-photosynthesis-print-bg-off-2.png` (greyscale, background off). |
| P4 | Key idea label read "note" or the writer's title | **fixed** `2a5e189a` | Adapter now labels every key idea "Key idea", matching Learn. |
| P5 | A key idea box split across pages 3 and 4 | **fixed** `2a5e189a` | `break-inside: avoid` on spanning asides. Re-rendered PDF moves the box intact. |
| P6 | Match-pairs task prints as a run-on prompt ("Items: ...; Possible matches: ...") over three blank answer lines, not as a lettered or two-column layout | **fixed** `14370a01`, `e1272d1b` | Print contract gained an optional `match {left, right}` on a questions item (additive, Print contract only; no shared-contract change). Printed as numbered items with a Match blank beside lettered answers in two columns; the right column is rotated so rows do not give the key away. Evidence: `fixes/pdf/images/phase5-photosynthesis-print-student-2.png`; teacher key reads "1 (water) -> C (...)" on `fixes/pdf/images/phase5-photosynthesis-print-bg-on-7.png`. |
| P7 | Practice tasks use three answer lines with no "I think this because" or "Explain your choice" line | acceptable | That line is specified for predict tasks (B4). The lesson has none. |
| P8 | Task header shows "QUESTION n - PRACTICE" with no right-hand label | acceptable | Spec text is "QUESTION n - PREDICT/CHECK". Right label is an artboard extra. |
| P9 | Misconception box prints correctly (grey header, belief / evidence / So rows) with no cross or tick marks | acceptable | Same as L5. |
| P10 | Teacher pages: the answer text is printed twice for Q2, Q3 and Q4 (answer, then an identical rubric paragraph) | **fixed** `e1272d1b` | The projection drops a rubric that only repeats the answer. Evidence: `fixes/pdf/images/phase5-photosynthesis-print-bg-on-7.png` (Q2 to Q4 print once) and `fixes/pdf/bg-on.txt`. |
| P11 | Teacher option notes end with internal misconception ids "(m1)", "(m2)", "(m3)" | **fixed** `e1272d1b` | Option notes cite displayed labels: ids that are option ids map to the letter, plan ids like "(m1)" are removed in the Print task projection only; shared data unchanged. Evidence: `fixes/pdf/images/phase5-photosynthesis-print-bg-on-7.png`. |
| P12 | Teacher answers sit on pages 7-8 of the same PDF, headed "Teacher copy - answer key"; artboard has a "TEACHER COPY" badge, an "Answers" title and "Question n - Role (page n)" headings | acceptable | Structure and content are present and separate from learner pages. The badge and per-question role headings are cosmetic. |
| P13 | The figure is a neutral grey placeholder with the caption below | acceptable | Doc 35 territory. Placeholder is evidence-only and in Print only. |
| P14 | Footer reads lesson title and "Page n of N" (artboard: same) | none | Matches. |

## Count

24 rows: 13 acceptable, 1 matching (P14), 10 fixed (L9, P4, P5 in Phase 5; L2, L8, L10, P3, P6, P10, P11 in the follow-up, evidence in `fixes/`), 0 to fix. The six pre-accepted items are not counted.

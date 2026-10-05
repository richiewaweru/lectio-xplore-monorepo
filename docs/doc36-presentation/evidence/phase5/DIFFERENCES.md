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
| L2 | Lesson map renders as wrapping cards (artboard: one row of small pills); in the card for section 2 the word "photosynthesis" touches the card edge | **to fix** (low) | Long section titles overflow the map item. Pills should truncate or wrap inside padding. Small CSS fix in `OrderedDocumentList.svelte`, not made (Track A file, cosmetic). |
| L3 | No subheadings, no ordered list, no equation, table or compare in the lesson | acceptable | Content choice. Writer advisory `shape_missing: section/subheading` was raised and not acted on, as doc 36 2.5 requires. |
| L4 | No figure (artboard has a pot illustration) | acceptable | Doc 35 territory. Provider returned 401. Learn renders nothing for a missing asset (A7). |
| L5 | Misconception cards show the writer's title ("The soil account") where the artboard shows "COMMON BELIEF 1"; no cross / tick marks beside "The belief" and "So" | acceptable | The label is the writer's own title text. The cross and tick are not in doc 36 section 2.1 and are absent from the golden fixture too. Cheap polish if the owner wants it. |
| L6 | Task header right-hand text is "PRACTICE" or "CHECK - CHOOSE ONE" (artboard "PREDICTION - NOT MARKED" or "CHECK - CHOOSE ONE") | acceptable | Mode text derives from the task role. This lesson has no predict task. The golden fixture shows "PREDICTION - NOT MARKED". |
| L7 | Primary button is salmon and faded before a choice is made (artboard shows full-strength orange) | acceptable | Disabled state until an answer exists. Enabled state is shown in `learn/phase5-q5-right-feedback.png`. |
| L8 | The correct-answer feedback has no leading check icon | **to fix** (low) | Section 3 says the "correct feedback icon" is green. Only the tinted panel is present. |
| L9 | Unordered list had no bullet markers in Learn (Tailwind preflight reset) | **fixed** `2a5e189a` | Bullets now render (`list-style: disc`). Print already had bullets. Evidence: `learn/phase5-photosynthesis-learn-1280.png` is the post-fix capture. |
| L10 | Match-pairs task renders two columns of buttons that carry no `aria-pressed` (selected state is a CSS class only) | **to fix** (low) | Keyboard check requires native buttons with a pressed state. Choice options are correct. Match items are not. File `InteractionShell.svelte`. |

## Print (artboards 2352c12b, c7001af4, 729a9f1d, 03f8091c)

| # | Difference | Mark | Reason |
|---|---|---|---|
| P1 | Page 1 holds title, Name, Date and a Contents list, then section 1 starts on page 2 (artboard: section 1 starts under the title) | acceptable | Contents list is allowed with five sections (B1). Page breaks differ (pre-accepted). Page 1 is left about 55% empty, which looks unfinished. |
| P2 | Name and Date are stacked lines under the title (artboard: on the title row) | acceptable | Layout choice; both lines present. |
| P3 | Key idea box is white with a 1px border (artboard: green tint) | **to fix** (low) | Doc 36 2.1 says "green tint plus 1px border". Distinguishable in greyscale by border and 18pt bold. Tint fill not applied. |
| P4 | Key idea label read "note" or the writer's title | **fixed** `2a5e189a` | Adapter now labels every key idea "Key idea", matching Learn. |
| P5 | A key idea box split across pages 3 and 4 | **fixed** `2a5e189a` | `break-inside: avoid` on spanning asides. Re-rendered PDF moves the box intact. |
| P6 | Match-pairs task prints as a run-on prompt ("Items: ...; Possible matches: ...") over three blank answer lines, not as a lettered or two-column layout | **to fix** | `print/generation/shared_document_adapter.py` lines about 314-315. Words are complete, so parity holds, but it reads poorly. Not a small change. |
| P7 | Practice tasks use three answer lines with no "I think this because" or "Explain your choice" line | acceptable | That line is specified for predict tasks (B4). The lesson has none. |
| P8 | Task header shows "QUESTION n - PRACTICE" with no right-hand label | acceptable | Spec text is "QUESTION n - PREDICT/CHECK". Right label is an artboard extra. |
| P9 | Misconception box prints correctly (grey header, belief / evidence / So rows) with no cross or tick marks | acceptable | Same as L5. |
| P10 | Teacher pages: the answer text is printed twice for Q2, Q3 and Q4 (answer, then an identical rubric paragraph) | **to fix** | Entry carries `answer` and `rubric` with identical text. Rendering should print the rubric only when it differs. |
| P11 | Teacher option notes end with internal misconception ids "(m1)", "(m2)", "(m3)" | **to fix** | Content authored by the task prompt (Track D), teacher-facing only, never on learner pages. Authoring should not cite plan ids. Left as generated. |
| P12 | Teacher answers sit on pages 7-8 of the same PDF, headed "Teacher copy - answer key"; artboard has a "TEACHER COPY" badge, an "Answers" title and "Question n - Role (page n)" headings | acceptable | Structure and content are present and separate from learner pages. The badge and per-question role headings are cosmetic. |
| P13 | The figure is a neutral grey placeholder with the caption below | acceptable | Doc 35 territory. Placeholder is evidence-only and in Print only. |
| P14 | Footer reads lesson title and "Page n of N" (artboard: same) | none | Matches. |

## Count

24 rows: 13 acceptable, 1 matching (P14), 3 fixed in this phase (L9, P4, P5), 7 to fix (L2, L8, L10, P3, P6, P10, P11). The six pre-accepted items are not counted.

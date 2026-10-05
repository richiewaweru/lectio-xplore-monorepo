# Doc 36 Track B (Print) - Gate G2 evidence

State after the lead's review round: the ten required print-look items are implemented and checked visually. G2 is **not ticked here**; the lead decides. Items are marked met or unmet with the evidence that supports the mark.

Method: the real Chromium route (`/fixtures/<id>?print=1&edition=...`) and `page.pdf` (A4, 16 mm margins, footer with lesson title and `Page n of N`), driven by `packages/lectio-page/scripts/render-fixture-pdf.ts` (`g2-pdf-render.log`). Golden, overlong and legacy page fixtures are re-exported from the real shared-to-Print adapter (`apps/textbook-agent/backend/scripts/export_shared_lesson_fixture.py`). Mechanical checks: `g2_checks.py` -> `g2-checks.json`; token parity: `check_text_parity.py` -> `text-parity-multiset.json`. Greyscale rasters (poppler `pdftoppm -gray`): `images/gray/`; colour rasters: `images/`; teacher PDF printed with background graphics off: `images/golden-teacher-bgoff-*.png`.

## The ten required items (lead review)

| # | Item | Status | Where to see it |
| --- | --- | --- | --- |
| 1 | Section header: 2px rule above, filled square number badge, bold Atkinson sans 16pt title; serif only for lesson title and quotes | done | `images/gray/golden-student-1.png` (section 1), `-2.png` (section 2), `-3.png` (3), `-4.png` (4) |
| 2 | Subheading: bold sans 12pt (16px), extra space above | done | `images/gray/golden-student-1.png` ("What you already know", "Two possible answers"), `-3.png` ("Follow the energy...", "So what is the soil for?") |
| 3 | Task: 2px border box, black header strip "QUESTION n . PREDICT / CHECK / PRACTICE" (mode omitted without a role), tick circles and lettered options, predict has "I think this because" with 2 answer lines, box kept together | done | `images/gray/golden-student-2.png` (predict), `-4.png` (check); `images/legacy-student-2.png` (no role: "QUESTION 1"); `images/golden-teacher-bgoff-4.png` (strip survives background off) |
| 4 | Ordered list: outlined numeral circles | done | `images/gray/golden-student-3.png`, `images/legacy-student-2.png` |
| 5 | Figure: 1px bordered frame, 13px caption starting "Figure n." | done | `images/gray/golden-student-1.png` |
| 6 | Misconception: bordered box, grey header "COMMON BELIEF n", rows The belief / The evidence / So (glyphs optional, none) | done | `images/gray/golden-student-3.png`, `-4.png` |
| 7 | Table: full 1px grid, grey `#EDEDED` header row, no all-caps | done | `images/gray/golden-student-3.png`; `images/golden-teacher-bgoff-3.png` (header stays grey with backgrounds off) |
| 8 | No hyphenation in body text (`hyphens: manual`) | done | `g2-checks.json` -> `line_end_hyphenation` is empty for all seven learner/teacher PDFs; the "predic-tion" and "en-ergy" breaks are gone in `images/gray/golden-student-2.png` |
| 9 | Footer: lesson title + "Page n of N"; Name/Date lines on page 1 | done | every page, e.g. `images/gray/golden-student-1.png`. The title moved from a top running head into the footer (left), page count at the right. |
| 10 | Teacher page shows the answer letter and option text, plus feedback and option notes | done | `images/gray/golden-teacher-5.png`: "Q2. A - A watered plant kept in darkness becomes pale and stops growing larger."; `images/overlong-teacher-7.png` |

Implementation notes: print CSS in `packages/lectio-page/src/lib/print/base-print.css` (synced to the contract copies and `sync-manifest.json`); `SectionView`/`LectioDocumentView` pass the section index to the badge; `ChoicesView`/`QuestionsView` render the task box and header from the block role (the strip is drawn for ids of the form `Q<n>`); `FigureView` wraps the image in a frame and prints "Figure n."; the render script's footer template carries the title. Fonts: the harness page now also loads Atkinson Hyperlegible from Google Fonts (400, 700, italic 400) and `.lectio-document` uses it, so headings and body are Atkinson in the PDFs (`pdffonts` confirms) instead of falling back to Arial. Backgrounds that carry meaning (strip, badge, header fills) use `print-color-adjust: exact` and survive printing with background graphics off.

Teacher answer entries are now inline runs "B - option text" (letter, em dash, option text; several correct options joined by "; "). `print/rendering/page_objects/validation.py` checks only the letters before the dash against the learner options. Option notes remain keyed by letter (earlier change).

## Defects found and fixed earlier in this pass

- Stale legacy page fixture (unsplit paragraphs) re-exported from the current adapter; stress fixture notes and answers aligned to adapter output.
- Header and footer flush to the page edge: 16 mm side padding.
- Choice letters overlapped option text; boxed asides touched the next paragraph.
- Teacher option notes showed raw option ids: keyed by displayed letter.
- Stale backend tests (inline written answers, 13 page objects, letter-and-text answers) updated.

## Test results (raw logs)

| Check | Result | Log |
| --- | --- | --- |
| Backend focused: Print adapter, inline lowering, shared fixture adapters/fixtures, teacher assembly and answer-key integrity, P11 Print cutover, contract sync | 39 passed | `g2-backend-focused.log` |
| `@lectio/page` vitest | 11 files, 65 passed | `g2-page-test.log` |
| `@lectio/page` svelte-check | 470 files, 0 errors, 0 warnings | `g2-page-check.log` |
| Full backend suite | not run (about 60 minutes); targeted only | n/a |

## G2 checklist

- [ ] **PDF of the golden fixture matches the canvas pages in structure. Lead decision.** Section headers, task boxes, framed figure, ordered-list circles, grid table, misconception box, footer and teacher page now follow the spec; the remaining differences from the artboards are the accepted ones listed below. Evidence: `pdf/shared-lesson-golden-student.pdf`, `pdf/shared-lesson-golden-bg-on.pdf`, `images/` against the artboards in `evidence/track-a/reference/` (branch `codex/doc36-learn`). Left unticked for the lead.
- [x] **Greyscale print: every block type still distinguishable. MET** by inspection of `images/gray/golden-student-1..4.png` and `golden-teacher-5.png`; the colour render has 0 coloured pixels (`g2-checks.json` -> `colour_pixels_in_colour_render_tol2`). Per block:
  - Title: large serif, Name/Date rules beneath. Section: 2px rule, filled black square number, bold sans title.
  - Prose: plain body text with bold emphasis; superscripts and subscripts render.
  - Figure: 1px frame around the image, caption "Figure 1." beneath.
  - Bullet list: disc markers. Steps: outlined numeral circles.
  - Callout ("Notice two things"): small thin-bordered box, bold label, smaller type.
  - Key idea: thin-bordered box, small label, 18pt bold text; separated from the callout by label and type size.
  - Equation: bordered box, "In one line" label, outlined term chips, operators and labelled arrow.
  - Compare: two side-by-side bordered cards with a caps label and bold card title.
  - Table: full grid with a grey bold header row.
  - Misconception: bordered grid, grey strip "COMMON BELIEF n", three ruled rows.
  - Quote: left rule, large serif text, small italic attribution beneath.
  - Task: 2px box with a solid black header strip "QUESTION n . ROLE", open circles with bold letters; predict adds a reason line and two rules.
- [x] **`overlong` fixture: more pages, no clipped or overlapping text. MET.** Learner 6 pages against golden 4 (teacher 7 against 5). Geometry from `pdftotext -bbox`: 0 words outside the 16 mm content width and 0 overlapping word pairs in every PDF, including `oversized-stress-student.pdf` (24 pages, 10,643 words). Token multiset parity: 0 missing tokens (`text-parity-multiset.json`, `all_pass: true`). Pages read: `images/overlong-student-1..6.png`, `overlong-teacher-1..7.png`.
- [x] **`legacy` fixture prints with paragraphs split and lists numbered. MET.** First block: 3 source paragraphs; page 1 shows 6 separate paragraph blocks; steps 1 to 5 appear as numeral circles (`g2-checks.json` -> `legacy`). `images/legacy-student-1..3.png`.
- [x] **Text search of the PDF finds none of "Choice-", section ids, `shared-node-`, `task-`. MET.** `g2-checks.json` -> `forbidden_string_hits`: empty for all seven learner and teacher PDFs. Limit: single plain-word ids (such as the intent "explain") cannot be told from prose, so only machine-shaped ids (hyphen, underscore or digit) are searched.
- [x] **No learner page contains an answer. MET.** `g2-checks.json` -> `learner_leakage`: none of the feedback, rubric, working or option-note texts appears in any learner PDF, and no "Teacher copy", "Answer key", "Feedback:", "Teacher note" or "Not marked" text. "I think this because" is a learner prompt.

Additional checks:

- [x] **Teacher page** says "Teacher copy", lists Q1 to Qn, shows predictions as "Prediction (not marked)" with "Not marked: accept either response.", shows letter and option text, explanatory feedback and an option-note table keyed by letter (`g2-checks.json` -> `teacher_page`).
- [x] **Q numbers on learner pages match the teacher page** (task header strips QUESTION 1 and 2 against Q1 and Q2 on the answer page, golden, overlong, stress): `g2-checks.json` -> `q_numbers`.
- [x] **Text parity**: every authored word is present in the PDF text (multiset with multiplicity; typed inline delimiters normalised). Not ordered parity, which is a Phase 5 item.
- [x] **Background toggle**: teacher PDFs have equal page counts with background on and off (`pdf/pdf-fixture-report.json`, render log).

## Differences from the artboards that remain (accepted by the lead, or caused by absent data)

1. No "SCIENCE - LESSON 1" eyebrow (the shared document has no subject or lesson-number field; no invented number).
2. Page breaks differ (4 learner pages against the artboard's 3: every shared word prints and boxes do not split).
3. Quote layout: left rule with the attribution beneath, where the artboard uses a tinted block with the lead-in above.
4. No cross and tick glyphs in the misconception box.
5. Name and Date are two full-width lines below the title rather than on one row beside the eyebrow.
6. The figure shows the reused Learn artwork without the reference labels and "Same in both pots" strip (doc 35 figure content boundary).
7. "Notice two things" is one paragraph in a box (data: the golden callout body is a paragraph); the artboard shows bullets.
8. Table first column is not bold; the "Explain your choice" lines do not appear (the golden check task has no explain prompt).
9. Teacher page: no badge or eyebrow, headings read "Q1." and no page references; no "A good explanation mentions" line (the shared task carries no such field).

## Evidence index

- PDFs: `pdf/` (golden learner, teacher with and without background, legacy, overlong, oversized stress, three Track C Print outputs, `pdf-fixture-report.json`).
- Page images: `images/` (colour) and `images/gray/` (greyscale) for golden learner and teacher, golden teacher with backgrounds off (colour and grey), legacy, overlong learner and teacher.
- Text extracts and `pdfinfo` per PDF: `*.txt`.
- Scripts: `g2_checks.py`, `check_text_parity.py` (set `POPPLER_BIN` to poppler's `bin` directory; the MSYS `pdftotext` is xpdf and mis-encodes UTF-8).

Equation `inputsMax`/`outputsMax` and compare `itemsMax` remain advisory; the stress fixture proves five inputs, four outputs and four cards render.

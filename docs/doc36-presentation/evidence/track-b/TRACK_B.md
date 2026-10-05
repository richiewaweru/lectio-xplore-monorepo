# Doc 36 Track B (Print) - Gate G2 evidence

State: re-verified after the final schema sync and the fixes listed below. G2 is **not ticked here**; the lead decides. Items are marked met or unmet with the evidence that supports the mark.

Method: the real Chromium route (`/fixtures/<id>?print=1&edition=...`) and `page.pdf` (A4, 16 mm margins, running head, `Page n of N` footer), driven by `packages/lectio-page/scripts/render-fixture-pdf.ts` (`g2-pdf-render.log`). Golden, overlong and legacy page fixtures are re-exported from the real shared-to-Print adapter (`apps/textbook-agent/backend/scripts/export_shared_lesson_fixture.py`) after the option-letter change. Mechanical checks: `g2_checks.py` -> `g2-checks.json`; token parity: `check_text_parity.py` -> `text-parity-multiset.json`. Greyscale rasters (poppler `pdftoppm -gray`): `images/gray/`; colour rasters: `images/`.

## Defects found and fixed in this pass

- The committed legacy page fixture was stale (one unsplit paragraph per block, plain strings, no `front_matter`), so the earlier legacy PDF did not prove paragraph splitting. It is re-exported from the current adapter; the PDF is now 3 pages with split paragraphs and a numbered list.
- Running head and footer were printed flush against the physical page edge (footer "Page 1 of 4" touched the right edge). The header/footer templates in the render script now carry 16 mm side padding.
- Choice letters overlapped the option text ("A.The plant ..."): hanging indent widened to 12 mm.
- Key-idea and callout boxes touched the following paragraph: spanning asides now have a bottom margin of one line.
- Teacher option notes showed raw option ids (`soil`, `b`, `c`, `d`): now keyed by the displayed option letter (see below).
- Backend tests that had gone stale against doc 36: written answers are inline runs (`test_p11_print_shared_document_cutover.py`), and the Page object catalogue has 13 objects (`test_lectio_page_contracts.py`).

## Option-letter change

`print/generation/shared_document_adapter.py`: `_choice_task` now also returns its option-id-to-letter map, and `_teacher_task_details` uses it so `option_notes` keys become A, B, C... in the Print answer entry. Shared data and shared fields are unchanged; question-type tasks (no letters) keep their keys. Test: `test_print_adapter_projects_doc36_blocks_and_shared_inline_markup` asserts every note key is a single capital letter and no raw id key remains. Teacher page: `images/gray/golden-teacher-5.png`, `images/overlong-teacher-7.png`.

## Test results (raw logs)

| Check | Result | Log |
| --- | --- | --- |
| Backend focused: Print adapter, inline lowering, shared fixture adapters/fixtures, teacher assembly and answer-key integrity, P11 Print cutover, contract sync | 39 passed | `g2-backend-focused.log` |
| `@lectio/page` vitest | 11 files, 65 passed | `g2-page-test.log` |
| `@lectio/page` svelte-check | 470 files, 0 errors, 0 warnings | `g2-page-check.log` |
| Full backend suite | not run (about 60 minutes); targeted only | n/a |

## G2 checklist

- [ ] **PDF of the golden fixture matches the canvas pages in structure. UNMET, lead decision needed.** Block order, section order, content and question numbering match; the visible structural differences from the artboards are listed in the next section (section numerals, task header bar and box, figure card, Name/Date placement, among others). Evidence: `pdf/shared-lesson-golden-student.pdf`, `pdf/shared-lesson-golden-bg-on.pdf`, `images/golden-*.png` against the artboards in `evidence/track-a/reference/` (on branch `codex/doc36-learn`).
- [x] **Greyscale print: every block type still distinguishable. MET** by inspection of `images/gray/golden-student-1..4.png` and `golden-teacher-5.png` (and `g2-checks.json` -> `colour_pixels_in_colour_render_tol2`: 0 coloured pixels, so the colour and greyscale renders are the same). Per block:
  - Title: large serif, Name/Date rules beneath; section titles: serif, larger than body, with space above.
  - Prose: plain body text; bold inline emphasis; superscripts and subscripts render (m^2, CO2).
  - Figure: image with a bold "Figure 1:" caption line below.
  - Bullet list: disc markers; numbered steps: "1." to "4." with a hanging indent.
  - Callout ("Notice two things"): small boxed block, bold label, smaller type.
  - Key idea: boxed block, small label "Key idea", then 18 pt bold text. Distinguished from the callout by label and type size, not only by the box.
  - Equation: boxed, "In one line" label, each term in its own outlined chip, operators between them, labelled arrow.
  - Compare: two side-by-side boxed cards, caps label ("ANSWER A"), serif card title.
  - Table: full grid, shaded header row in caps.
  - Misconception: bordered grid with shaded header strip ("Common belief 1") and three ruled rows (The belief, The evidence, So).
  - Quote: left rule, large serif text, small italic attribution beneath.
  - Tasks: bold "Q1."/"Q2." number, open circles with bold letters, "I think this because:" with a rule on the predict task.
  - Weak point: tasks have no container box and no role label, so a task is told apart only by its Q number and circles (see differences).
- [x] **`overlong` fixture: more pages, no clipped or overlapping text. MET.** Learner 6 pages against golden 4 (teacher 7 against 5): `g2-checks.json` -> `page_counts`, `overlong_more_pages_than_golden: true`. Geometry (word boxes from `pdftotext -bbox`): 0 words outside the 16 mm content width and 0 overlapping word pairs for every PDF, including `oversized-stress-student.pdf` (25 pages, 10,778 words). Token multiset parity: 0 missing tokens for overlong (1,762 learner / 1,930 teacher) and the stress fixture (`text-parity-multiset.json`). Pages inspected: `images/overlong-student-1..6.png`, `overlong-teacher-1..7.png`. Large unused areas on pages 5 and 6 appear because tasks and boxes do not split, as designed.
- [x] **`legacy` fixture prints with paragraphs split and lists numbered. MET.** `g2-checks.json` -> `legacy`: the first block has 3 source paragraphs and page 1 shows 6 separate paragraph blocks; list items 1 to 5 are numbered. `images/legacy-student-1..3.png`.
- [x] **Text search of the PDF finds none of "Choice-", section ids, `shared-node-`, `task-`. MET.** `g2-checks.json` -> `forbidden_string_hits`: empty for all seven learner and teacher PDFs. Limit: ids made of a single plain word (for example the intent "explain") cannot be separated from prose, so only machine-shaped ids (containing a hyphen, underscore or digit) are searched.
- [x] **No learner page contains an answer. MET.** `g2-checks.json` -> `learner_leakage`: none of the answer-key feedback, rubric, working or option-note texts appears in any learner PDF, and none of "Teacher copy", "Answer key", "Feedback:", "Teacher note", "Not marked" appears. The answer line "I think this because:" is a learner prompt, not an answer.

Additional doc 36 checks (Track B items B1 to B6):

- [x] **Teacher page** says "Teacher copy", lists Q1 to Qn, shows predictions as "Prediction (not marked)" with "Not marked: accept either response.", shows explanatory feedback and an option-note table keyed by letter: `g2-checks.json` -> `teacher_page`.
- [x] **Q numbers on learner pages match the teacher page** (golden, overlong, stress: Q1, Q2 on both): `g2-checks.json` -> `q_numbers`.
- [x] **Text parity**: every authored word is present in the PDF text (multiset with multiplicity; hyphenated wraps and typed inline delimiters normalised). Not ordered parity, which is a Phase 5 item: `text-parity-multiset.json` (`all_pass: true`).
- [x] **Background toggle**: teacher PDFs have equal page counts with background on and off (golden 5/5, overlong 7/7, stress 26/26): `pdf/pdf-fixture-report.json` and the render log.

## Structural differences from the artboards

Compared with `reference/2352c12b...` (page 1), `c7001af4...` (page 2), `729a9f1d...` (page 3) and `03f8091c...` (teacher answers). Doc 36 wins over the artboards where they conflict; items marked (data) come from the shared document rather than the renderer.

1. No "SCIENCE - LESSON 1" eyebrow. The shared document has no subject or lesson-number field (data; no invented number).
2. Name and Date are two full-width lines under the title, not beside the eyebrow on one row. The artboard's heavy rule under the title is absent.
3. Section titles have no black numeral square and no bold sans title with a heavy rule above; they are serif, regular weight. Subheadings ("What you already know") are serif regular rather than bold sans.
4. The figure is a bare image with a "Figure 1:" caption, not a framed two-panel card with a "Same in both pots" strip. The reused Learn figure lacks the reference labels (doc 35 figure content boundary).
5. The predict task has no dark header bar ("QUESTION 1 - PREDICT", "NOT MARKED"), no bordered task box and one answer line instead of two. The check task likewise has no box or role label, and the artboard's "Explain your choice" lines do not appear (the golden check task has no explain prompt, data).
6. Numbered steps print as "1." to "4." instead of circled numerals.
7. "Key idea" label is sentence case rather than all caps; fill is not tinted (greyscale design).
8. "Notice two things" is a single paragraph in a box, where the artboard shows a bulleted list in a tinted box (data: golden callout body is one paragraph and carries the added m^2 note).
9. Table header cells are all caps and the first column is not bold, where the artboard uses title-case headers and bold row labels.
10. Misconception rows have no cross and tick glyphs and the header strip reads "Common belief 1" without the artboard's treatment of the caps label and glyph column.
11. Quote has a left rule with the attribution below ("A student says"), where the artboard uses a tinted block with the lead-in line above.
12. Running line: the lesson title is in the running head on every page and the footer carries only "Page n of N", where the artboard puts the title in the footer left. The teacher footer has no "Teacher copy" text.
13. Teacher answer page: title "Teacher copy - answer key" without the artboard's badge and "SCIENCE - LESSON 1" line; headings read "Q1." rather than "Question 1 - Predict (page 1, not marked)"; no page references; the answer prints as the option letter only ("Q2. A") without the option text; the note table header reads "Option / Teacher note" instead of "Why it does not challenge the soil idea"; no "A good explanation mentions" line (the shared task carries no such field).
14. Length: 4 learner pages against the artboard's 3, because every shared word is printed and tasks and boxes do not split (required by doc 36).

## Evidence index

- PDFs: `pdf/` (golden learner, teacher with and without background, legacy, overlong, oversized stress, three Track C Print outputs, `pdf-fixture-report.json`).
- Page images: `images/` (colour) and `images/gray/` (greyscale) for golden learner and teacher, legacy, overlong learner and teacher.
- Text extracts and `pdfinfo` per PDF: `*.txt`.
- Scripts: `g2_checks.py`, `check_text_parity.py` (set `POPPLER_BIN` to poppler's `bin` directory; the MSYS `pdftotext` is xpdf and mis-encodes UTF-8).

The shared document does not carry a separate authored subject or lesson-number field. The running head therefore uses the normalised lesson title, with no internal id or invented lesson number. Equation `inputsMax`/`outputsMax` and compare `itemsMax` remain advisory; the stress fixture proves five inputs, four outputs and four cards render.

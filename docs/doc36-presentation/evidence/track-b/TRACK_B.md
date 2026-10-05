# Doc36 Track B print evidence

The Print path is exercised through the real Chromium route (`/fixtures/<id>?print=1&edition=...`) and `page.pdf`, with A4 CSS page size, 16 mm page margins, grayscale styling, local fixture media, and Chromium page number templates.

| Gate | Evidence |
| --- | --- |
| B1/B3 ordinary blocks and inline markup | `shared-lesson-golden-student.pdf` and `shared-lesson-golden-bg-on.pdf`; DOM coverage is checked by `scripts/render-fixture-pdf.ts`. |
| B2 front matter/running line/footer | PDFs contain Name/Date fields, the lesson running head on every page, and `Page n of N` footer text. |
| B4 learner paper | Student PDFs contain prompts, options, and answer lines without teacher answer-key content. |
| B5 safe oversized continuation | `oversized-stress-student.pdf` is 25 pages and contains a 34,800-character prose block, 120 table rows, four comparison cards, a tall misconception, and five-input/four-output equation. Page 25 begins at the reserved content area and has no clipping. |
| B6 answer separation | Teacher PDFs include `Answer key`; student text has no answer-key, feedback, or predict-answer leak tokens. |
| G2 text parity | `text-parity-answer-separation.json`: 0 missing learner tokens for golden (729 words) and stress (9,225 words). Hyphenated line endings are joined for extraction comparison. |
| G2 grayscale | `grayscale-check.json`: 29 rendered page images, 0 non-grayscale pixels beyond a 2-channel-value rasterisation tolerance. |
| background toggle | Teacher background on/off PDFs have equal page counts (golden 5/5, stress 26/26). |

The shared document does not carry a separate authored subject or lesson-number field. The running head therefore uses the normalized lesson title, with no internal ID or invented lesson number.

Equation `inputsMax`/`outputsMax` and compare `itemsMax` remain advisory catalogue guidance. They are not validation or rendering rejection limits; the stress fixture proves five inputs, four outputs, and four comparison cards render and validate.


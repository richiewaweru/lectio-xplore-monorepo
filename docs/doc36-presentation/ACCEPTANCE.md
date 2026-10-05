# Final acceptance: doc 36

Status: Phase 5 evidence recorded on `codex/doc36-integration`. Owner sign-off is not given. A ticked box has linked evidence. An unticked box carries its reason.

Phase 5 headline: the fresh photosynthesis run completed every text stage but did **not** reach READY, because its one required figure failed with image-provider HTTP 401 (doc 35 blocks finalization on a failed required figure). Learn and Print evidence below comes from the text-only draft that the pipeline's own assembler produced from the accepted outputs (hash `d0c3f54f...460cbf`), shown through the dev fixture routes. Full record: [evidence/phase5/PHASE5.md](./evidence/phase5/PHASE5.md). Differences against the artboards: [evidence/phase5/DIFFERENCES.md](./evidence/phase5/DIFFERENCES.md).

## Owner checklist (section 5)

- [ ] Fresh Learn resembles the canvas: reading column, numbered section headers, key ideas, three-part misconceptions, dark task headers. Visually all five are present in [the 1280 capture](./evidence/phase5/learn/phase5-photosynthesis-learn-1280.png) and [the 390 capture](./evidence/phase5/learn/phase5-photosynthesis-learn-390.png). Not ticked because the lesson never reached READY and was opened through the dev fixture route, not a stored lesson. Visible shortfalls are listed as L2, L8 and L10 in DIFFERENCES.md.
- [ ] The same lesson PDF resembles the worksheet, with a separate teacher answer page. Structure is present: [learner PDF](./evidence/phase5/pdf/phase5-photosynthesis-print-student.pdf), [teacher PDF](./evidence/phase5/pdf/phase5-photosynthesis-print-bg-on.pdf) with answers on pages 7 and 8. Not ticked: rendered through the page fixture route with a placeholder figure, not the Print worker. Open items P3, P6, P10 and P11.
- [x] Learn and Print ordinary blocks have identical words. 12 of 12 text blocks identical in order; the figure caption differs only because Learn renders nothing for an asset-less figure (A7). [parity.json](./evidence/phase5/parity.json).
- [ ] Paragraph breaks, numbered lists, bold, subscripts and equations render in both. Paragraph breaks and bold are proven on the fresh lesson in both outputs. Numbered lists, sub/superscripts and equations were not chosen by this lesson, so they are not proven on fresh output (golden fixture only, Tracks A and B). [PHASE5.md section 6](./evidence/phase5/PHASE5.md).
- [x] Learner outputs show no internal ids, counts, version or interaction-type labels. DOM text and attribute scans in [learn-dom-report.json](./evidence/phase5/learn/learn-dom-report.json); PDF text scans in [pdf-checks.log](./evidence/phase5/pdf/pdf-checks.log). Teacher option notes no longer carry "(m1)" style ids (P11 fixed, [teacher page](./evidence/phase5/fixes/pdf/images/phase5-photosynthesis-print-bg-on-7.png)).
- [x] Length/shape overages cause only advisory warnings; no failure or regeneration. Run events show no shape or length retry, repair or regeneration. The warnings raised are listed in [PHASE5.md section 2](./evidence/phase5/PHASE5.md). The Run's block at media is unrelated to length or shape.
- [x] Stored lessons still open and print with unchanged hashes. Legacy hash recomputed equal to `44ab7dbe...fd3b6b`, Learn opens and answers, PDF prints: [legacy-hash.log](./evidence/phase5/legacy-hash.log), [legacy Learn](./evidence/phase5/learn/legacy-learn-1280.png), [legacy PDF](./evidence/phase5/pdf/shared-lesson-legacy-student.pdf).
- [x] Phone-width Learn has no horizontal page scroll. False for all three fixtures at 390 in [learn-dom-report.json](./evidence/phase5/learn/learn-dom-report.json).
- [ ] G0-G4 evidence is attached to track PRs: desktop/mobile screenshots, PDFs, advisory logs and downgraded-check list. The evidence is committed in this repository (see the gate ledger). No PR has been opened or updated by Phase 5, so this stays unticked.

Owner sign-off: ____________________ (unsigned)

## Gate ledger

| Gate | Status | Summary and evidence |
| --- | --- | --- |
| G0 | Accepted | RUNBOOK.md; committed regression logs and legacy PDF. Phase 5 re-run: Ruff cleared (29 errors, [log](./evidence/phase5/backend-ruff.log)), architecture check clean ([log](./evidence/phase5/architecture.log)), frontend check/build/tests and page tests green. Full backend suite not run, by instruction. |
| G1 | Accepted, with Phase 5 findings | A: `4525b64d`, `879b3cff`, `856dc4c2`; six fixture screenshots, DOM checks and keyboard traversal. Phase 5 re-checked on the fresh lesson, legacy and golden at 1280 and 390: no horizontal scroll, no ids, `aria-pressed` choice buttons ([learn/](./evidence/phase5/learn/)). Found and fixed: Learn unordered lists had no bullets (`2a5e189a`). Fixed after Phase 5: match-pairs items now have `aria-pressed` (L10), lesson-map chips wrap (L2), correct feedback has a green check (L8); evidence in [fixes/learn/](./evidence/phase5/fixes/learn/). |
| G2 | Accepted, with Phase 5 findings | B: `eed18c86` and corrections `353d1747`. Phase 5: fresh lesson PDF has no `Choice-`, `shared-node-`, `task-` text, no answer on learner pages, nothing clipped, greyscale distinguishable ([pdf/](./evidence/phase5/pdf/)). Found and fixed: key idea label and a split key-idea box (`2a5e189a`). Fixed after Phase 5: match-pairs print layout (P6), duplicated teacher answers (P10), key idea tint (P3); evidence in [fixes/pdf/](./evidence/phase5/fixes/pdf/). |
| G3 | Partly met on the fresh whole-lesson run | C: `087e3daf`, `b3bb27c6`, `7dbb01ad`. The deferred key-idea item is now evidenced: both explaining sections (`criteria`, `contrast`) open with a filled key-idea callout of 23 and 24 words ([g3_g4_checks.json](./evidence/phase5/g3_g4_checks.json)). Misconceptions arrive in three parts (2 of 2). No run failed or regenerated because of length or shape. This run has no subscript, superscript, equation, table or compare, so those G3 items rest on Track C's earlier area and compare runs, not on this one. The `apply` section raised `shape_missing key_idea`, which is advisory. The run did not reach READY (media 401). |
| G4 | Met on the fresh run and golden | D: `8ab204b6` to `07812dd8`. Fresh run: all 5 `display_prompt`s one sentence and none repeats the paragraph above; no generic "Correct." or "Not yet" feedback strings; check-task feedback is explanatory ([learn/interaction.log](./evidence/phase5/learn/interaction.log)). Predict never shows Correct or Not yet: shown on the golden fixture because the fresh lesson authored no predict task. Old stored tasks answer (legacy Q1 and Q2). Question numbers match across Learn, learner Print and the teacher page: Q1 to Q5 in all three. |

Track draft PRs: [A - Learn #6](https://github.com/richiewaweru/lectio-xplore-monorepo/pull/6), [B - Print #7](https://github.com/richiewaweru/lectio-xplore-monorepo/pull/7), [D - Tasks #8](https://github.com/richiewaweru/lectio-xplore-monorepo/pull/8), [C - Writer #5](https://github.com/richiewaweru/lectio-xplore-monorepo/pull/5). Each targets the Phase 0 branch. Integration is on `codex/doc36-integration` ([evidence/integration/INTEGRATION.md](./evidence/integration/INTEGRATION.md)). Nothing has been merged to main.

## Visual differences to review

Pre-accepted by the lead:

| Difference | Decision | Evidence / rationale |
| --- | --- | --- |
| Existing Fraunces display serif instead of canvas Newsreader | Acceptable | Doc 36 explicitly requires the existing app serif. |
| Full shared wording instead of abbreviated Print text; page count may differ | Acceptable | Doc 36 requires word parity and permits different page breaks. |
| No subject or lesson-number eyebrow | Acceptable | The data is absent from the shared document. |
| Golden fixture adds the superscript note "Leaf area can be measured in m^2^." | Acceptable | Mandatory grammar coverage absent from the reference; fixture only. |
| Figure lacks reference labels | Acceptable | Doc 35 territory. |

Phase 5 findings from the artboard comparison: 24 rows, 13 acceptable, 1 matching, 3 fixed in this phase, 7 fixed afterwards (evidence in `evidence/phase5/fixes/`), none open. See [DIFFERENCES.md](./evidence/phase5/DIFFERENCES.md). All seven to-fix rows (L2, L8, L10, P3, P6, P10, P11) are now fixed.

## Current review findings

- The only blocker to a fully real-route acceptance is an environment fault: every image credential in the dev `.env` is rejected. With one working credential, the Run `f4a02de5-f74c-40df-827a-59e2fe87beb2` has one media retry left; after it finalizes, Learn and Print can be recaptured through the real routes with the same text. Until then items 1, 2 and 4 above stay unticked.
- C's whole-lesson Track C runs (area, compare) remain the evidence for subscript, superscript and equation rendering from fresh generation; the photosynthesis run did not use them.
- Known advisory misses retained, not repaired: Track C's summary-style list item in the earlier photosynthesis run; this run's `length_over_target` (3 paragraphs) and missing subheadings (4 sections).

## Execution branches

Accepted Phase 0: `92973aa0` on `codex/doc36-phase0`; supplemental production guard evidence `21cc2ede`.
Tracks branched from the accepted commit. Merge order: 0, A, B, D, C, integrated on `codex/doc36-integration`. No main push.

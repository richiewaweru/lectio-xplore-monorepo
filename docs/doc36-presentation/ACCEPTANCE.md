# Final acceptance — doc 36

Status: pending track gates and Phase 5. An empty checkbox has no acceptance evidence yet.

## Owner checklist (section 5)

- [ ] Fresh Learn resembles the canvas: reading column, numbered section headers, key ideas, three-part misconceptions, dark task headers.
- [ ] The same lesson PDF resembles the worksheet, with a separate teacher answer page.
- [ ] Learn and Print ordinary blocks have identical words.
- [ ] Paragraph breaks, numbered lists, bold, subscripts and equations render in both.
- [ ] Learner outputs show no internal ids, counts, version or interaction-type labels.
- [ ] Length/shape overages cause only advisory warnings; no failure or regeneration.
- [ ] Stored lessons still open and print with unchanged hashes.
- [ ] Phone-width Learn has no horizontal page scroll.
- [ ] G0–G4 evidence is attached to track PRs: desktop/mobile screenshots, PDFs, advisory logs and downgraded-check list.

## Gate ledger

| Gate | Status | Evidence |
| --- | --- | --- |
| G0 | Accepted | RUNBOOK.md; committed regression logs and legacy PDF |
| G1 | Accepted | A: `4525b64d`, `879b3cff`, `856dc4c2`; six fixture screenshots, DOM checks and all-task keyboard traversal |
| G2 | Corrections required | B: `eed18c86`; initial golden/stress PDFs reviewed; missing list markers, question numbering and prediction lines |
| G3 | Evidence incomplete; quality misses retained | C: `087e3daf`; 122 focused tests, three live generations, accepted exports and Learn captures |
| G4 | In progress | Track D |

Track draft PRs: [A — Learn #6](https://github.com/richiewaweru/lectio-xplore-monorepo/pull/6), [B — Print #7](https://github.com/richiewaweru/lectio-xplore-monorepo/pull/7), [D — Tasks #8](https://github.com/richiewaweru/lectio-xplore-monorepo/pull/8), [C — Writer #5](https://github.com/richiewaweru/lectio-xplore-monorepo/pull/5). Each targets the Phase 0 branch. No track has been integrated or merged into main.

## Visual differences to review

| Difference | Decision | Evidence / rationale |
| --- | --- | --- |
| Existing Fraunces display serif instead of canvas Newsreader | Acceptable | Doc 36 explicitly requires the existing app serif. |
| Full shared wording instead of abbreviated Print text; page count may differ | Acceptable | Doc 36 requires word parity and permits different page breaks. |
| Golden fixture adds the superscript note "Leaf area can be measured in m^2^." | Acceptable | Mandatory grammar coverage absent from reference; fixture only. |

Append actual screenshot/PDF findings after visual review; do not infer acceptance from these intended exceptions.

## Current review findings

- A's final golden desktop/mobile captures preserve block order, quote misconception beliefs, put the aside below its box, and show no horizontal page overflow. Full keyboard evidence is being extended to both tasks.
- B's initial PDFs need visible list markers, question numbers, tick circles, prediction answer lines, the prescribed key-idea typography and table grid. The figure must reuse the supplied fixture asset; figure redesign is outside this work order. Legacy and frozen overlong PDF evidence is still required.
- C's three accepted outputs are one-section composer/writer runs, not Phase 5's complete end-to-end lesson. The formula section lacks a key idea. None of the three contains a subscript/superscript or a misconception. Golden coverage cannot satisfy those fresh-generation items. These misses must remain visible; accepted content is not repaired or regenerated for shape.

## Execution branches

Accepted Phase 0: `92973aa0` on `codex/doc36-phase0`; supplemental production guard evidence `21cc2ede`.
Tracks branch from the accepted commit and remain isolated until their gates are reviewed. Merge order: 0 → A → B → D → C. No main push.

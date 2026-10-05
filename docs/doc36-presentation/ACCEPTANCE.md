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
| G1 | Pending | Track A |
| G2 | Pending | Track B |
| G3 | Pending | Track C |
| G4 | Queued | Track D |

## Visual differences to review

| Difference | Decision | Evidence / rationale |
| --- | --- | --- |
| Existing Fraunces display serif instead of canvas Newsreader | Acceptable | Doc 36 explicitly requires the existing app serif. |
| Full shared wording instead of abbreviated Print text; page count may differ | Acceptable | Doc 36 requires word parity and permits different page breaks. |
| Golden fixture adds the superscript note "Leaf area can be measured in m^2^." | Acceptable | Mandatory grammar coverage absent from reference; fixture only. |

Append actual screenshot/PDF findings after visual review; do not infer acceptance from these intended exceptions.

## Execution branches

Accepted Phase 0: `92973aa0` on `codex/doc36-phase0`; supplemental production guard evidence `21cc2ede`.
Tracks branch from the accepted commit and remain isolated until their gates are reviewed. Merge order: 0 → A → B → D → C. No main push.

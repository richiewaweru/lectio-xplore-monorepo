# Track D evidence â€” task presentation and Learn behavior

Worktree: `codex/doc36-tasks` (Phase 0 base `92973aa0`).

## G4 checklist

Closed 2026-10-05 by the Track D implementer; the lead decides acceptance.

- [x] Fresh task authoring keeps a short `display_prompt` and does not repeat more than one sentence from the context above it. Evidence: [`g4-prompt-overlap.log`](g4-prompt-overlap.log) / [`g4-prompt-overlap-report.json`](g4-prompt-overlap-report.json) — every task has 0 repeated sentences, except live `task-predict-light` which has 1 (the allowed maximum) against its sourcebook/plan text. Limit: the live run authors tasks only, so no authored paragraph exists in the live JSON; the live prompts are checked against the writer's inputs (bound sourcebook entries plus plan block brief/evidence) and against the paragraph above each anchor in the composed documents (golden skeleton). Legacy prompts, which fold the setup into the prompt, are legacy data and are not the authoring target.
- [x] A predict task never shows `Correct` or `Not yet`. Evidence: real Chromium run [`g4-browser-proof.log`](g4-browser-proof.log) with screenshots [`images/golden-predict-1-before.png`](images/golden-predict-1-before.png), [`-2-selected`](images/golden-predict-2-selected.png), [`-3-saved`](images/golden-predict-3-saved.png) (shows `Prediction saved. Keep it in mind — Part 2 will test it.`) and [`-4-other-option-saved`](images/golden-predict-4-other-option-saved.png) (the other option is saved with no grading either). Both options PASS.
- [x] Old stored (role-absent) tasks still render and can be answered. Evidence: same log; [`images/legacy-1-before.png`](images/legacy-1-before.png), [`legacy-2-correct-answer`](images/legacy-2-correct-answer.png) (`Correct.`), [`legacy-3-wrong-answer`](images/legacy-3-wrong-answer.png) (`Not yet`). Both legacy tasks render as Q1/Q2.
- [x] No fresh feedback string equals `Correct.` or `Not yet — try again.`. Evidence: [`g4-feedback-strings.log`](g4-feedback-strings.log) — five feedback strings in the topical live JSON, all explanatory; zero exact legacy strings and zero occurrences of `Not yet`.
- [x] Running Q numbers agree across Learn, learner Print and the teacher answer page. Evidence: [`g4-numbering-run.log`](g4-numbering-run.log) / [`g4-numbering-report.json`](g4-numbering-report.json), produced by [`g4_numbering_harness.py`](g4_numbering_harness.py): golden `Q1,Q2`, legacy `Q1,Q2`, live topical `Q1,Q2,Q3` are identical across Learn, Print learner blocks, Print answer-key entries and Print task metadata, with the same anchor/task behind each number. No mismatch was found. Cross-checks: the browser log shows Learn's rendered `data-question-number` sequence `Q1,Q2` for golden and legacy, and Track B's committed teacher/learner PDF text for golden shows `Q1.`/`Q2.` (`codex/doc36-print:docs/doc36-presentation/evidence/track-b/shared-lesson-golden-*.txt`).

### Numbering harness (how it works, and its limits)

The tracks are not merged, so the harness runs the two real adapters in separate processes over the same stored shared-lesson documents:

- Learn side: this branch's `realize_shared_document_for_learn`, then the `DocumentCanvas.svelte` rule (one running counter over every `interaction` node in document order).
- Print side: `realize_shared_document_for_print` from `codex/doc36-print` (353d1747), extracted read-only with `git archive` into a scratch directory; no Track B file is modified. Learner numbers are the `Q<n>` block ids, teacher numbers the `answer_key` `question_id`s.
- Inputs ([`g4-numbering-inputs/`](g4-numbering-inputs/)): golden and legacy fixtures, plus a composed document that anchors the three live DeepSeek tasks (`predict`, `practice`, `check`, in live order) into the golden skeleton.
- Limits: figure nodes are removed from the harness copies because Print admission needs produced figure media (figures carry no numbering); the live document reuses golden paragraphs because the live run authored tasks only; the check compares emitted numbering from the adapters, not rendered Print PDFs of the live document. It is not a Phase 5 merged-output proof.
- Re-run: `JWT_SECRET_KEY=<any 32+ chars> python g4_numbering_harness.py run --print-tree <dir containing the archived apps/textbook-agent/backend/{src,contracts,resources}>` (about one minute).

## Focused implementation evidence

- Backend: [`focused-backend.log`](focused-backend.log) â€” 55 focused tests passed; one existing Pydantic warning.
- Frontend unit tests: [`focused-frontend-tests.log`](focused-frontend-tests.log) â€” 4 tests passed.
- Frontend static check: [`frontend-check.log`](frontend-check.log) â€” 0 errors, 5 pre-existing warnings.
- Advisory audit: [`advisory-record.log`](advisory-record.log) records one provider call, preserved overlong strings, and exact non-blocking paths/counts (`display_prompt` 30/25 and `feedback.correct` 41/40); [`advisory-log.log`](advisory-log.log) captures the warning channel.
- Runtime prediction uses the existing `pending-review` outcome with `0/0` scores, neutral details, and authored `saved` feedback after validating the response.
- Legacy role-absent Learn adapter behavior remains covered by the existing adapter assertions (`Correct.` / `Not yet â€” try again.`).
- Default DeepSeek structured mode is now `prompted_json`; strict tool support remains explicit and tested.

## Fresh provider evidence

- [`g4-d-live-photosynthesis-20261005-1852-json.json`](g4-d-live-photosynthesis-20261005-1852-json.json) â€” accepted live DeepSeek prompted-JSON output for one unique, revision-bound photosynthesis Teaching Plan with three fresh tasks (`predict`, `practice`, and `check`). It retains the authentic sourcebook facts, approved item snapshot, meaningful option text, explanatory feedback, and teacher-only wrong-option notes.
- The earlier accepted files [`g4-d-live-20261005-1832-json.json`](g4-d-live-20261005-1832-json.json), [`g4-d-live-20261005-1835-predict-json.json`](g4-d-live-20261005-1835-predict-json.json), and [`g4-d-live-20261005-1839-check-json-retry.json`](g4-d-live-20261005-1839-check-json-retry.json) are retained as provider diagnostics but excluded from topical quality evidence because their fact text was placeholder content.
- [`g4-d-live-provenance.json`](g4-d-live-provenance.json) retains the exact approved Teaching Plans, sourcebooks, and revision-bound snapshots used for the earlier diagnostic runs; the topical run retains its own provenance in its JSON document.
- [`g4-d-live-20261005-1824.json`](g4-d-live-20261005-1824.json) records the initial prompted-JSON hard-schema failure (`response: Field required`) with two provider calls; it is retained as failure evidence. [`g4-d-live-20261005-1828-strict.json`](g4-d-live-20261005-1828-strict.json) is a strict-tool diagnostic only and is excluded from G4 acceptance.

## Browser/rendered evidence

- [`browser-proof.txt`](browser-proof.txt) records the local Learn golden prediction save and role-absent legacy answer proof from the real browser. The Learn AX tree showed the authored question, paragraph context, saved prediction feedback, and no correctness feedback for prediction.
- [`g4-browser-proof.log`](g4-browser-proof.log) plus [`images/`](images/) hold the screenshot-backed version of the same proof (script [`g4_browser_proof.cjs`](g4_browser_proof.cjs), real Chromium via the repo's existing Playwright install, dev fixture routes on a local Vite server that was stopped afterwards).
- Print and teacher Q-number agreement is evidenced by the isolated harness above, not by merged output; merged-output confirmation stays with Phase 5.


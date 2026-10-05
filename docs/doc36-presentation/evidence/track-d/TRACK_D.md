# Track D evidence — task presentation and Learn behavior

Worktree: `codex/doc36-tasks` (Phase 0 base `92973aa0`).

## G4 checklist

- [x] Fresh task authoring retains a short `display_prompt` and does not repeat more than one sentence from the paragraph above. The topical photosynthesis run below contains distinct prompts for prediction, practice, and checking.
- [x] Prediction submissions are saved with the existing ungraded `pending-review` representation and never expose correct/incorrect state in focused runtime/component tests.
- [x] Fresh practice/check feedback is explanatory; no accepted fresh record uses the legacy generic `Correct.` or `Not yet — try again.`.
- [x] Previously stored role-absent tasks still render and answer with legacy behavior. Browser proof in [`browser-proof.txt`](browser-proof.txt) shows the legacy `Check` path and `Correct.` feedback.
- [ ] Running Q numbers agree across Learn, learner Print, and the teacher answer page.

## Focused implementation evidence

- Backend: [`focused-backend.log`](focused-backend.log) — 55 focused tests passed; one existing Pydantic warning.
- Frontend unit tests: [`focused-frontend-tests.log`](focused-frontend-tests.log) — 4 tests passed.
- Frontend static check: [`frontend-check.log`](frontend-check.log) — 0 errors, 5 pre-existing warnings.
- Runtime prediction uses the existing `pending-review` outcome with `0/0` scores, neutral details, and authored `saved` feedback after validating the response.
- Legacy role-absent Learn adapter behavior remains covered by the existing adapter assertions (`Correct.` / `Not yet — try again.`).
- Default DeepSeek structured mode is now `prompted_json`; strict tool support remains explicit and tested.

## Fresh provider evidence

- [`g4-d-live-photosynthesis-20261005-1852-json.json`](g4-d-live-photosynthesis-20261005-1852-json.json) — accepted live DeepSeek prompted-JSON output for one unique, revision-bound photosynthesis Teaching Plan with three fresh tasks (`predict`, `practice`, and `check`). It retains the authentic sourcebook facts, approved item snapshot, meaningful option text, explanatory feedback, and teacher-only wrong-option notes.
- The earlier accepted files [`g4-d-live-20261005-1832-json.json`](g4-d-live-20261005-1832-json.json), [`g4-d-live-20261005-1835-predict-json.json`](g4-d-live-20261005-1835-predict-json.json), and [`g4-d-live-20261005-1839-check-json-retry.json`](g4-d-live-20261005-1839-check-json-retry.json) are retained as provider diagnostics but excluded from topical quality evidence because their fact text was placeholder content.
- [`g4-d-live-provenance.json`](g4-d-live-provenance.json) retains the exact approved Teaching Plans, sourcebooks, and revision-bound snapshots used for the earlier diagnostic runs; the topical run retains its own provenance in its JSON document.
- [`g4-d-live-20261005-1824.json`](g4-d-live-20261005-1824.json) records the initial prompted-JSON hard-schema failure (`response: Field required`) with two provider calls; it is retained as failure evidence. [`g4-d-live-20261005-1828-strict.json`](g4-d-live-20261005-1828-strict.json) is a strict-tool diagnostic only and is excluded from G4 acceptance.

## Browser/rendered evidence

- [`browser-proof.txt`](browser-proof.txt) records the local Learn golden prediction save and role-absent legacy answer proof from the real browser. The Learn AX tree showed the authored question, paragraph context, saved prediction feedback, and no correctness feedback for prediction.
- Print and teacher Q-number agreement remains unticked until B's projection and answer-key changes are integrated.


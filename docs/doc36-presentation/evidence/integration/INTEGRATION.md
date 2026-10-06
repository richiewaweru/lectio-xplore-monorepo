# Doc 36 integration (branch `codex/doc36-integration`)

Base: `origin/codex/doc36-phase0` (cddb436c). Merge order: doc 35 tip, A, B, D, C. Each merged with `--no-ff`.

## Merge commits
| Step | Source | Result |
|---|---|---|
| 1 | `origin/fix/media-truth-execution` (c080dbcd) | clean, no conflicts |
| 2 | `origin/codex/doc36-learn` (Track A, 856dc4c2) | clean |
| 3 | `origin/codex/doc36-print` (Track B, c3a1d685) | clean |
| 4 | `origin/codex/doc36-tasks` (Track D, 07812dd8) | 3 conflicts, resolved below |
| 5 | `origin/codex/doc36-writer` (Track C, e491d081) | 2 conflicts, resolved below |

## Conflicts and resolutions
Track D (frontend):
- `DocumentCanvas.svelte`: kept A's question-number expression (honours `interactionOffset` across sections). Dropped D's `questionNumbers` map, so there is one counter.
- `InteractionNodeRenderer.svelte`: kept A's version (EOL-only differences in the other hunks).
- `InteractionShell.svelte`: kept A's markup (native `<button>` options with `aria-pressed`, one dark task header, typography, `Check my answer` label). Transplanted D's behaviour: `savePrediction` import and `normalizeFeedback(node.feedback, role)`. D's auto-merged saved-prediction state, graded-feedback suppression and submit handling are present. `display_prompt` falling back to `prompt` was already in A. D's radio-role markup was not restored.

Post-merge fixes (commit `fix(integration)` and a later one, found by tests and evidence):
1. `lib/shared/auth/routing.ts`: A gated `/dev/shared-lesson/` to dev mode. D separately added an unconditional line, and the two auto-merged together, defeating the gate (`routing.test.ts` failed). Removed D's unconditional line.
2. `InteractionShell.test.ts` (D's test): queried `role=radio`. It now queries the native button and asserts `aria-pressed`.
3. `InteractionNodeRenderer.svelte`: A's version had dropped the `data-interaction-type`, `data-node-id` and `data-question-number` hooks that D's tests and evidence rely on. The hooks are non-visual and were restored on the wrapper `<section>`. The structure is unchanged.

Track C (backend):
- `finalizer.py`: both sides fixed the same warnings-hash divergence with identical code. Kept HEAD's comment.
- `test_shared_lesson_finalizer.py`: took C's `section_warnings={"s1": previous_warnings}`, which C's warnings test needs.
- `composer.py` and the two prompts merged without textual conflicts. Doc 35 figure logic and C's key-idea slot (`EXPLAINING_INTENTS`, `KEY_IDEA_SLOT_PREFIX`, `reserve_key_idea`) coexist.

B/D boundary: no new shared fields. The shared->Print adapter output for the golden fixture after the merge is byte-identical (as parsed JSON) to Track B's committed `packages/lectio-page/fixtures/shared-lesson-golden.json`.

## Test results
- App `pnpm check`: 0 errors, 5 pre-existing warnings. App `pnpm test`: 70 files, 296 tests passed (final run). App build (`vite build`) succeeded.
- Page package: `page:check` 0 errors; `page:test` 11 files, 65 tests passed. This needed `@lectio/contracts` built first (`pnpm build` in `packages/lectio-contracts`; dist is untracked).
- Backend targeted, after merges 1-4: 338 passed (shared_lesson contract/inline/fixtures/adapters/finalizer/task runtime/run-failure/media/continuity/worker/dispatcher/review-submit, `tests/learn`, Print adapter, closed task contract, p10c runtime, shared task feedback contract, lesson progress, `tests/media`, `tests/contracts`, p10b cutover).
- Backend after merge 5 (C): 192 passed (composer, writer, finalizer, continuity, QA runtime, document QA dispatcher, post-section pipeline, work-item inputs, composer/writer admission, figure consistency, figure executor adapter, prompt resources). Ruff on the 12 files changed by C: clean.
- Full backend suite was not run (about 60 min), per instructions.

## Evidence (this folder)
Captured against the dev fixture routes, `vite dev` on 5188. Scripts: `capture_learn.cjs`, `capture_task_proof.cjs`. Logs: `learn-capture.log`, `integration-browser-proof.log`, `pdf-render.log`.
- Golden Learn: `images/golden-learn-1280.png`, `images/golden-learn-390.png`; legacy: `images/legacy-learn-1280.png`, `images/legacy-learn-390.png`. No horizontal overflow. One task header per task (2 tasks).
- Keyboard traversal: `learn-capture.log` and `images/golden-keyboard-focus.png`. Tab reached all 6 options (all `aria-pressed`, no radio roles) and both actions (`Lock in my prediction`, `Check my answer`). Space toggled `aria-pressed` to true.
- Golden prediction saved: `images/golden-predict-1-before.png`, `-2-selected.png`, `-3-saved.png`, `-4-other-option-saved.png`. The message is "Prediction saved. Keep it in mind". Neither "Correct" nor "Not yet" appears for either option. PASS.
- Legacy task answering: `images/legacy-1-before.png`, `legacy-2-correct-answer.png` (Correct.), `legacy-3-wrong-answer.png` (Not yet). PASS.
- `data-question-number` sequence: golden ["1","2"] and legacy ["1","2"], at both 1280 and 390.
- Print: `pdf/shared-lesson-golden-student.pdf` (4 pages), `pdf/shared-lesson-golden-bg-on.pdf` and `-bg-off.pdf` (teacher, 5 pages each), same as Track B's counts. Extracted text: learner shows QUESTION 1, QUESTION 2. The teacher page shows Q1 "Prediction (not marked)" and Q2 as "A - <option text>" with feedback and option notes. Numbering agrees across Learn, learner Print and teacher.

I read the 1280 and 390 Learn captures and the saved-prediction screenshot. Layout, header strip, option letters and saved message look right.

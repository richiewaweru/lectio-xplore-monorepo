# Phase 5 evidence: integration run and acceptance

Branch `codex/doc36-integration`. Executor: Phase 5. Ports 5189 (frontend) and 8015 (backend). Both processes were stopped by PID afterwards (backend 40584, frontend 21680 and its child) and the ports were verified free.

## 1. Validators

| Check | Result | Log |
|---|---|---|
| `python tools/agent/validate_repo.py --scope all` | Not run as one command. The `all` scope includes `uv run pytest` (the full backend suite, about 60 minutes), which the brief excludes. Its steps were run individually: backend Ruff green (it was 29 errors, not 30), tooling pytest and the touched backend tests green, frontend `check` 0 errors (5 pre-existing warnings), frontend `build` done, frontend vitest 70 files / 296 tests, `@lectio/page` 11 files / 65 tests and `check` 0 errors. | `backend-ruff.log`, `lint-targeted-tests.log`, `frontend-check.log`, `frontend-build.log`, `frontend-test.log`, `page-test.log`, `page-check.log`, `backend-print-adapter-tests.log` |
| `python tools/agent/check_architecture.py --format text` | "No architecture violations found." | `architecture.log` |

Lint fixes (`1646c2bd`, EOLs preserved, `git diff --stat` shows 1:1 line counts): unused imports removed (`curriculum/planning/persistence.py`, three v3_execution tests); 15 star-import compatibility shims carry `# noqa: F403 - compatibility re-export shim`; two `tests/conftest.py` imports carry `# noqa: E402` (they must follow the env defaults); `test_shared_run_admission_postgres.py` declares `pytest_plugins` after its imports. No global ignores.

## 2. Generation (real Unit pipeline, DeepSeek in prompted JSON mode)

- Driver: `tools/drive.py` (Track C's, repointed to this worktree and port 8015). Server: `tools/run_server.py` with `DEEPSEEK_STRUCTURED_MODE=prompted_json`.
- Unit `d6f28a62-b528-4ee9-af51-db9fa2a7b3b4`, topic "How Plants Get the Energy to Grow". The planner produced six lessons. The driver's keyword scorer picked "Explaining how plants grow: putting the process together" (lesson `cfe2697f-de31-4642-afe1-79a5be199868`; teaching plan learner title "How a plant makes its own food: light, water and air in the leaves"). Preparation generation `910bef47-fcc3-4eca-a8a4-845c986d2d99`.
- SharedDocument Run `f4a02de5-f74c-40df-827a-59e2fe87beb2`.
- **READY reached: NO.** All text stages completed (sourcebook, tasks, five composers, five writers, four boundary checks). The one required figure then failed in media generation with `provider_http_401` (the Gemini image endpoint, invalid token). The product's own Retry was used once and gave a second 401. The third attempt was not spent: the other image credentials in `.env` were probed and also rejected (xAI 403, OpenAI 401). Under doc 35 a failed required figure blocks Document QA and finalization, so no stored SharedLessonDocument exists. Per the brief the media failure is recorded, not fixed. Evidence: `fullrun-photosynthesis/learn-status-history*.json`, `events.json`, `retry-response-1.json`.
- **Fallback used for everything below.** `tools/assemble_draft.py` calls the pipeline's own loader and `assemble_shared_lesson_document` over the durably accepted composer and writer outputs, with no media. Deterministic QA returned ready. The draft is `fullrun-photosynthesis/shared-document.json`, id `shared-document:f4a02de5-f74c-40df-827a-59e2fe87beb2:revision:1`, **content hash `d0c3f54f7cd7647a74842dd8f5ac5499390625e520278eb21d340cb774460cbf`**. It never passed document QA or finalization. No content was edited.
- Provider calls: 20 DeepSeek calls (`deepseek-flash`), all HTTP 200 with `finish_reason: stop`, none carrying `tools` or `response_format`; 2 Gemini image calls, both 401. See `provider-calls-summary.json`; raw bodies are in `run/provider-calls-raw.jsonl`. No Authorization header was captured, and a scan of this folder against the `.env` secret values found only provider base URLs.
- Work items: 18 ready, 2 failed (both the media item), 1 retry queued (media). No shape or length retry, repair or regeneration. Events: `section_write_warning` x4, `composition_style_warning` x1 (`fullrun-photosynthesis/events.json`).
- Advisory warnings (all kept, none acted on), from `fullrun-photosynthesis/draft-assembly.json`:
  - orient: `length_over_target nodes[0].text 104/60`
  - criteria: `length_over_target nodes[1].text 168/60`; `shape_missing section/subheading`
  - contrast: `length_over_target nodes[2].text 148/60`; `shape_missing section/subheading`; composer `section_exceeds_callout_limit choices[2].kind`
  - apply: `shape_missing section/key_idea`; `shape_missing section/subheading` (apply is not an explaining section, so this key-idea miss is the writer-side shape check, not the code-reserved slot)

## 3. Learn

Route used: the dev fixture route `/dev/shared-lesson/phase5-photosynthesis`, registered in this phase for evidence. No auth path to a stored document exists because the Run did not finalize. Scripts: `tools/capture_learn.cjs`, `tools/capture_interaction.cjs`. Output in `learn/`.

- Full-page screenshots: `learn/phase5-photosynthesis-learn-1280.png` and `-390.png`; legacy `learn/legacy-learn-1280.png`, `-390.png`; golden `learn/golden-learn-1280.png`, `-390.png`.
- DOM checks (`learn/learn-dom-report.json`), all three fixtures at both widths: no horizontal scroll; none of section ids, `shared-node-`, `task-`, `shared-key-idea`, `shared-figure`, `Choice-`, "nodes", "V2" or "DOCUMENT" in visible text; none in any non-class attribute; no literal `**`, `~` or `^`.
- Keyboard (`learn/interaction.log`): choice options are native `<button>` elements with `aria-pressed` and no radio role. Space toggles pressed. Tab runs through the options then "Check my answer". Match-pairs items are buttons without `aria-pressed` (difference L10 in DIFFERENCES.md).
- Feedback: on the check task a wrong option shows explanatory guidance only and the right option shows an explanatory message (`learn/phase5-q5-right-feedback.png`). Neither shows "Correct." or "Not yet". Open-response tasks show their message after any text (`learn/phase5-q2-feedback.png`). The generated lesson has no predict task, so the predict check ran on the golden fixture: both options show "Prediction saved. Keep it in mind" and neither shows Correct or Not yet.

## 4. Print

Path: the backend shared-to-Print adapter (`realize_shared_document_for_print`), then the `@lectio/page` `LectioDocumentView` route and Playwright `page.pdf`. This is the same chain Track B used. It is not the Print worker, which needs a stored document. The adapter requires bound media for the required figure, so a neutral placeholder image (`fullrun-photosynthesis/figure-placeholder.svg`) was bound, using the same verification bypass as Track B's `export_shared_lesson_fixture.py`. The placeholder is in Print only.

- PDFs: `pdf/phase5-photosynthesis-print-student.pdf` (6 pages); teacher `pdf/phase5-photosynthesis-print-bg-on.pdf` and `-bg-off.pdf` (8 pages, answers on pages 7 and 8); legacy `pdf/shared-lesson-legacy-student.pdf` (3 pages). PNG rasters are in `pdf/images/` and greyscale rasters in `pdf/images/gray/`. Text dumps and `pdfinfo` sit beside the PDFs.
- `pdf/pdf-checks.log`: learner, teacher and legacy text contain none of `Choice-`, `shared-node-`, `task-`, `V2`, "nodes", or section id lines. No answer, feedback or option-note string appears on learner pages, and no "Teacher copy", "answer key" or "Feedback:". Teacher option notes contain "(m1)" style ids (P11).
- `pdf/margin-check.log`: no ink in the outer margins of any page of any PDF, so nothing is clipped.
- Greyscale: task header strips, bordered key ideas, grey-headed misconception grids, numbered section badges and lettered tick options stay distinguishable (`pdf/images/gray/`).

## 5. Word parity (`parity.json`, `tools/parity.py`)

Learn rendered DOM text per block against the learner PDF text, in order. Chrome labels (KEY IDEA and the three misconception row labels) are stripped on both sides.

- 13 non-task blocks: 12 identical in order, 0 differ. The 13th is the figure. Learn renders nothing for an asset-less figure (A7) while Print renders frame and caption. This is expected.
- Tasks (display prompt and options, 5 tasks): no part is missing from Learn or Print. Print's match-pairs prompt adds connective text ("Match each item to its pair. Items: ... Possible matches: ...", P6) where Learn shows the same words in columns.
- Key idea label: Learn "KEY IDEA". Print said "note" or the writer's title until the fix in `2a5e189a`; it now says "Key idea". The parity run above used the post-fix PDF.

## 6. Formatting

- Paragraph breaks: Learn splits into separate `<p>` elements (nodes of 2, 4 and 3 paragraphs). Print shows separated paragraphs.
- Bold: 15 `<strong>` spans in Learn; bold key terms and bold opening sentences are visible in Print. No literal `**`, `~` or `^` in either (DOM and PDF text).
- Numbered lists, subscripts, superscripts, equations: **not exercised by this lesson**. It has one unordered list and spells out "carbon dioxide". Learn bullets were missing and are fixed (L9). Numbered lists, sub/superscripts and equations are covered on the golden fixture by Tracks A and B (`../track-a/`, `../track-b/`, `../integration/`) and on Track C's earlier full runs. They are not claimed from this run.

## 7. Key idea and prompt repetition (`g3_g4_checks.json`)

- Explaining sections under the code-reserved slot rule (`EXPLAINING_INTENTS`): `criteria` (define) and `contrast` (explain-cause). Both open with a filled `key_idea` callout (23 and 24 words, both within 25). orient, apply and check are not explaining sections and open with a paragraph. Result: 2 of 2 explaining sections pass.
- G4 item 2: 5 tasks. Each `display_prompt` is one sentence of 7 to 17 words. None repeats a sentence of the paragraph above it (exact or 0.9 fuzzy). `task-contrast-b1` has no preceding paragraph; it follows callouts. No feedback string is "Correct." or "Not yet - try again.". Roles: four practice, one check, no predict.

## 8. Legacy (`legacy-hash.log`)

- The fixture content hash was recomputed as `44ab7dbe3e048881eda5d6fd15062b82a7a13394b87c66a9a63e2a4706fd3b6b`. It equals the expected value and the stored `content_hash`.
- It opens in Learn (`learn/legacy-learn-1280.png`, `-390.png`): paragraphs split, five-step list numbered, section titles visible, no ids. Its two tasks answer: Q1 wrong option "Not yet - try again.", right option "Correct." (stored legacy feedback is unchanged by design). See `learn/interaction.log`.
- It prints: `pdf/shared-lesson-legacy-student.pdf`, 3 pages, paragraphs split, no forbidden strings, no margin ink.

## 9. Renderer fixes made in this phase (small, within doc 36)

Commit `2a5e189a`: Learn unordered-list bullets (`ListNode.svelte`); Print key idea label "Key idea" (adapter); `break-inside: avoid` for spanning asides (`base-print.css`, its three synced copies and the backend contract manifest). After the fixes: backend print adapter tests 32 passed, contract tests 6 passed, page tests 65 passed, frontend tests 296 passed.

## 10. Evidence harness changes (dev only)

Dev fixture `phase5-photosynthesis` is registered in `routes/dev/shared-lesson/[fixture]/+page.ts` and `+server.ts` (with `src/lib/learn/document/dev-fixtures/phase5-photosynthesis.json`). Page fixture `phase5-photosynthesis-print` is registered in `packages/lectio-page` (fixtures, `src/lib/fixtures.ts`, `scripts/render-fixture-pdf.ts`, `static/phase5-figure-placeholder.svg`). Production guards are unchanged (`dev` only).

## 11. Dev database rows

Unit `d6f28a62-b528-4ee9-af51-db9fa2a7b3b4` and its path, preparation generation, Runs, work items and events remain in the local dev Postgres under user `whole-lesson-proof-runner`. The Run stays `failed_recoverable` with one media retry attempt left. Once a working image credential exists, that retry should let the Run finalize, and the real Learn and Print routes can be captured without regenerating any text.

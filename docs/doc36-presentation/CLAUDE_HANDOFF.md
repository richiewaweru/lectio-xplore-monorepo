# Doc 36 implementation handoff — 5 October 2026

This is a checkpoint report, not final acceptance. Read doc 36 in full, the user's approved plan, and this report before continuing. Doc 36 wins over the supplied artboards. Work has been checkpointed for transfer; no track has been merged into the integration branch or main.

## Current status

| Work | Actual status |
|---|---|
| Verification / section 9 | Completed and reported. |
| Phase 0 / G0 | Implemented, tested and accepted by the lead. |
| A / G1 Learn | Implemented; G1 accepted by the lead with screenshots, DOM and keyboard evidence. |
| B / G2 Print | Implementation and corrected PDFs checkpointed. Final lead review, post-sync backend checks and updated gate report still pending. G2 is not accepted. |
| C / G3 Writer | Implementation and three live one-section generations checkpointed. Fresh-generation quality/coverage items remain unmet. G3 is not accepted. |
| D / G4 Tasks | Implementation, live topical JSON-mode tasks, focused tests, advisory logs and browser notes checkpointed. Cross-output numbering proof remains pending. G4 is not accepted. |
| Integration / Phase 5 | Not started. Do not infer end-to-end acceptance from isolated track tests. |

## Branches and exact checkpoints

Repository: `https://github.com/richiewaweru/lectio-xplore-monorepo.git`.

Start/reference branch was `fix/media-truth-execution`, reviewed committed base `901cce27`. It was not merged into local main. The separate ongoing Doc 35 checkout is `C:\Projects\lectio-media-truth`; do not reset, clean or modify it. Later Doc 35 work is not automatically part of this implementation.

All four tracks branch from accepted Phase 0 commit **`92973aa0`**. The coordination branch has additional reports, not merged renderer implementations.

| Branch | Checkpoint | Local checkout | Draft PR |
|---|---|---|---|
| `codex/doc36-phase0` | `a6cc694a` before this handoff report commit | `C:\Users\richi\.codex\worktrees\e983\lectio` | Base for the four PRs |
| `codex/doc36-learn` | `856dc4c210a579dac6ebd314d132f4a0da362f01` | `C:\Users\richi\.codex\worktrees\doc36-learn\lectio` | [A #6](https://github.com/richiewaweru/lectio-xplore-monorepo/pull/6) |
| `codex/doc36-print` | `353d1747d916f88df0ab1ad1e78f622785438674` | `C:\Users\richi\.codex\worktrees\doc36-print\lectio` | [B #7](https://github.com/richiewaweru/lectio-xplore-monorepo/pull/7) |
| `codex/doc36-writer` | `0e8191b555541bd621ffe006a3915431eb7bae02` | `C:\Users\richi\.codex\worktrees\doc36-writer\lectio` | [C #5](https://github.com/richiewaweru/lectio-xplore-monorepo/pull/5) |
| `codex/doc36-tasks` | `4619e4882037f4b21463aae2824046b197cd4b05` | `C:\Users\richi\.codex\worktrees\doc36-tasks\lectio` | [D #8](https://github.com/richiewaweru/lectio-xplore-monorepo/pull/8) |

Track checkouts were clean at handoff. The lead checkout has untracked earlier/duplicate logs, PDFs and `tmp/`; do not stage everything. Its authoritative G0 evidence is already committed. Fetch the latest remote branches and inspect status before editing; the report commit advances the coordination branch beyond the snapshot above.

## Decisions that must survive the handoff

- Word and shape numbers are prompt targets only. Preserve every word, equation term and comparison card. No failure, repair, regeneration, truncation, padding or READY change because of length/shape. Record advisory warnings.
- The owner explicitly made equation input/output and comparison-card **upper bounds advisory** too. Meaningful structural minimums remain schema checks.
- DeepSeek uses **JSON output mode**, with local validation. Do not switch to strict tool/schema mode to cure failures. D changes the configuration default and example to `prompted_json`; explicit strict capability remains in existing infrastructure, but is not the execution mode for this job.
- Preserve old authored content and hashes. Newly introduced absent defaults are omitted from legacy canonical serialization; existing null serialization is not globally changed.
- Doc 35 owns figure decisions. Do not invent new illustrations or undo its code-owned figure handling.
- Existing Fraunces display serif and Atkinson body text; only doc 36's palette, kinds and libraries.
- No learner-facing internal IDs/counts/version labels/placeholders. Semantic part/question/page numbering required by the design is retained.
- Normal Print blocks stay together. Intrinsically oversized blocks continue at safe text/row boundaries without clipping, shrinking or losing words.
- Shared declarations are frozen at G0. A owns task structure/styles, D behaviour/data; B owns Print/Page rendering. Contract changes require lead review.
- Keep one PR per track, no pushes to main. Merge order is **0 → A → B → D → C**, after all required gates pass, then one executor for Phase 5. Unticked items stay unticked.

## Completed implementation and evidence

Paths below are relative to the relevant branch checkout.

### Phase 0 — accepted

Added shared callout variants (retaining legacy `tone`), equation/quote/compare, task presentation fields on the shared task contract and adapter propagation. TaskAnchor linkage is retained. Python and TypeScript inline parsers use identical vectors, escaped rendering boundaries and literal malformed-markup fallback. Golden, authentic legacy and overlong fixtures plus development-only Learn/PDF proof routes are present; production guard proof returns 404 for preview routes/assets.

Key files: backend `src/document/shared_lesson/{models,inline,fixtures}.py`, `src/curriculum/shared_tasks/models.py`; frontend `src/lib/learn/document/{types,inline}.ts` and `dev-fixtures/`; backend `scripts/export_shared_lesson_fixture.py`.

Authentic legacy source/export are committed under `docs/doc36-presentation/evidence/legacy-{shared-source,learn-export}.json`. Stored shared-document hash remains **`44ab7dbe3e048881eda5d6fd15062b82a7a13394b87c66a9a63e2a4706fd3b6b`**. Stored source identity: `shared-document:7ea5d498-3550-4259-a9b8-66da3a3f9fdb:revision:1`.

G0 evidence: 2,015 backend tests passed, 5 skipped, 7 deselected; 281 frontend tests; 64 Page tests; 20 contract tests; identical parser vectors passed. Frontend check: zero errors/five existing warnings; architecture: no violations. See `RUNBOOK.md` and committed `g0-*` logs. Do not rerun the full backend suite merely to repeat G0 (it took about 64 minutes).

Local stored-data audit: 49/51 rows retained exact payloads/hashes. Two rows already invalid on unchanged main: `63bfd8ce-af34-4058-a539-3f833e1c5837` hash mismatch, `6c0bc034-3d99-4935-85df-827a6c10c6ec` missing wrong-option feedback. No stored row was modified/rehashed.

### A — G1 accepted

Reading column, section navigation/headers, all ordinary blocks, inline formatting, mobile layout, title/context cleanup, missing-asset hiding and text-only unknown-kind fallback implemented. Choice markup uses native buttons with `aria-pressed`; dark task headers are preserved. Dev-only auth routing exemption allows fixture capture without changing production auth.

Commits: `c34645b2`, `4525b64d`, `879b3cff`, `856dc4c2`. Evidence: `docs/doc36-presentation/TRACK_A.md` and `evidence/track-a/`. Six golden/legacy/overlong desktop/mobile screenshots; DOM no-overflow/leakage results; actual keyboard traversal across six options and both enabled actions. Full frontend 284 tests; final focused 14; check zero errors/five existing warnings; build passed.

`track-a/reference/` holds all five supplied artboard PNGs and provenance. `G3_LEARN.md` distinguishes fresh C captures from golden vocabulary coverage.

### B — checkpointed, G2 still pending

Shared-to-Print adapter, Python inline lowering, Page schema/generated twins, equation/quote/compare/callouts, full-width layout, pagination and separate teacher answer page implemented. Latest commit corrects missing list markers, Q numbers/circles, prediction line, figure prefix, key-idea sizing, misconception box/aside structure, table grid and white/greyscale surface. It reuses the supplied figure fixture asset.

Teacher assembly now retains feedback, option notes and neutral prediction handling. Lead reviewed the latest teacher page: it visibly says Teacher copy, Prediction (not marked), explanatory feedback and option-note tables. Other final pages still need complete lead review. Teacher option-note keys currently include raw IDs such as `soil`; consider mapping them to displayed option letters in task projection without changing shared data.

Evidence: `evidence/track-b/pdf/` contains golden learner/teacher, legacy, overlong, oversized stress and all three C Print outputs; `images/` contains rendered pages. `text-parity-multiset.json` reports all cases pass with token multiplicity. This is **not ordered ordinary-word parity**; Phase 5 still owes that. Stress covers oversized prose, 120 table rows, four cards and five-input/four-output equation. Page logs: 65 tests, check zero errors/warnings.

Important remaining work: run/capture targeted backend tests after the final schema sync; finish visual/greyscale/clipping/leakage review of the corrected set; update the stale `TRACK_B.md` checklist (it still describes the earlier checkpoint); update PR #7. Executor reported a prior adapter run of 10 passing tests, not a fresh post-sync result. The initial PDFs had real visual failures; do not rely on their earlier pass claims.

### C — implemented, G3 not accepted

Composer/writer prompts and schemas carry new vocabulary/shaping guidance. Length/count/run/callout checks are advisory; former shape auto-fixes removed. Warnings propagate through work-item/post-section/QA quality flags. Mixed semantic shape plus leakage keeps leakage actionable while dropping only the shape finding. Identity/schema/leakage/task checks retain established behaviour. Doc 35 figure ownership retained.

Evidence `evidence/track-c/`: 122 focused tests, Ruff/compilation pass, raw provider requests/responses, accepted SharedLessonDocument/Learn exports and warning summary. Three live composer/writer generations used photosynthesis, rectangle formula and photosynthesis/respiration comparison; one composer plus one writer call each. These are **one-section cases, not complete Unit lesson end-to-end runs**.

Unmet G3: formula explaining section has no key idea (`shape_missing section/key_idea`); all three fresh outputs have no subscript/superscript and no misconception. Golden proves renderer support but does not clear fresh-generation requirements. Fresh science/comparison key ideas appear after their equation/cards rather than opening the section. Accepted content remains unchanged; no shape reruns or manual additions were made. No lists in those cases, so no summary-list item was observed. Keep these misses explicit; do not manufacture a green gate by rerunning because of shape.

### D — checkpointed, G4 numbering pending

Authoring prompt adds roles/display prompts/explanatory feedback/teacher notes and explicit advisory targets. Prediction response validation returns existing `pending-review`, zero/zero scores and saved feedback. Replay is neutral even on its exception path; outer V2 presentation fields survive nested-contract fallback. Client suppresses graded server feedback for predictions. Role-absent legacy behaviour retained. No new public enum or shared declaration added.

Evidence `evidence/track-d/`: 55 focused backend tests, four frontend tests, check zero errors/five existing warnings; topical live `g4-d-live-photosynthesis-20261005-1852-json.json` with predict/practice/check and actual sourcebook facts. Earlier generic test-fact runs are diagnostics only; the earlier strict diagnostic is excluded from acceptance. `browser-proof.txt` records actual golden prediction saved feedback and legacy `Correct.` answering, but is a textual browser record rather than screenshots. Advisory audit records preserved 30/25 display words and 41/40 feedback words, with warning logs; treat it as deterministic audit evidence, not proof of a fresh live overage.

G4 is still unticked for Q-number agreement across Learn, learner Print and teacher page. Complete that with the real topical tasks, paragraph repetition check and teacher-note projection. Do not require merging the tracks just to claim the prerequisite gate; use an isolated acceptance harness/projection as needed and document it.

## Integration hazards and remaining acceptance

Read `INTEGRATION_REVIEW.md`. A/D conflict in three Svelte files: `InteractionShell.svelte`, `DocumentCanvas.svelte`, `InteractionNodeRenderer.svelte`. Keep A's accepted markup/styles/native pressed buttons; transplant D behaviour and one running Q counter. Blindly taking D's Phase 0 markup would restore radio roles and regress G1. B/D task projection boundary remains to be reconciled.

Phase 5 remains entirely pending: complete photosynthesis generation, merged Learn at 1280/390, learner/teacher PDFs, ordered ordinary-word parity, legacy hash/render/answer checks, task/metadata results, advisory logs and comparison against all five artboards. Run `python tools/agent/validate_repo.py --scope all` and `python tools/agent/check_architecture.py --format text` after integration. G0 recorded 30 pre-existing Ruff errors (compatibility imports/setup ordering/unused imports); fix narrowly, not by global ignores. Existing Svelte warnings remain documented.

Section 5 owner acceptance remains unsigned in `ACCEPTANCE.md`; no complete fresh lesson/merged validation has been certified. Isolated successes must not be represented as final acceptance.

Known design differences: Fraunces instead of Newsreader (required/acceptable); full shared Print wording/more pages (required/acceptable); golden adds `Leaf area can be measured in m^2^.` for grammar coverage (fixture-only); reused Learn figure lacks some reference labels/legend (Doc 35 figure content boundary, record explicitly); subject/lesson-number context unavailable in stored shared export, so no invented number. Final difference list still pending.

## Practical restart

1. Fetch branches/PRs; read doc 36, this report, RUNBOOK, ACCEPTANCE and track evidence. Preserve clean checkpoints and ongoing Doc 35 work.
2. Finish B's post-sync checks/report and final visual review; finish D's cross-output numbering and review remaining proof limits.
3. Resolve/report G3's genuine unmet acceptance items without rewriting or regenerating accepted content for shape. Do not silently waive the gate.
4. Only after gates are accepted, integrate in the prescribed order, resolve A/D conflicts carefully, then run Phase 5 and fill every owner acceptance/difference item with evidence.

Use backend Python at `C:\Projects\lectio\apps\textbook-agent\backend\.venv\Scripts\python.exe` with `PYTHONPATH` set to the **current worktree's** backend `src`; otherwise editable imports can target main. Use existing pnpm/Playwright PDF tooling, no new libraries. Keep `.env`/provider credentials private and uncommitted. Track executors have stopped editing; D's owned Vite 5184 was stopped, B reports no owned preview server. Local DB/service infrastructure may still be running for other work; do not kill unrelated processes.

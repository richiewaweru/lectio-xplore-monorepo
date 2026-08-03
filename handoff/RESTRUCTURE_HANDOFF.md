# RESTRUCTURE_HANDOFF.md

**Status:** authoritative. Supersedes any conflicting guidance in `handoff/00–19` for the items in scope here. Everything not named in this document stays exactly as it is.

**Branch:** `xplore`. **Date:** 2026-08-02.

---

## 1. Scope and non-goals

This restructure has three goals: make stage 2 fast, make the product speak teacher language end to end, and make prompts loadable/visible/editable. It preserves the architecture that the beta audit confirmed working.

**Non-goals — do not touch:**

- Stage 1 structural planner: prompt, reasoning level (high), model slot, output schema. Untouched.
- The wall: quiz items generated from concept cards only, shared item set across versions. Untouched. Its prompt is extracted to a file but locked view-only.
- The halt: no auto-approval path anywhere. The lesson-card confirmation screen replaces the plan-review presentation but the gate itself is unchanged.
- Path planner prompt and backward-decomposition logic. Untouched (it already nominates merge pairs — we now consume the nominations).
- Frozen published packs, path freeze on approval.
- Student-facing features. None. Learner data capture stays unscoped.

**Decisions recorded (do not re-litigate):**

1. The expander stays for now. Revisit only after measuring quality at low reasoning.
2. Merge critic runs on nominated pairs only.
3. Prompt editability v1: all viewable; `structural-planner` and `quiz-items` locked; the rest editable.
4. The constructor (readback) is in scope: LLM composes destination objective / starting knowledge / curriculum context from raw teacher text. The three form fields are deleted.

---

## 2. Workstream A — Stage 2 speed

### A1. Remove anchor-first serialization

`backend/src/v3_blueprint/planning/retry.py` (~line 219). Currently `plan.sections[0]` runs alone, then the rest fan out with the anchor's brief as `prior_briefs`. Change: fan out **all** sections in one `asyncio.gather`. Continuity context for every section comes from the structural plan itself (anchor name + `transition_notes`), passed into `build_stage2_user_message` in place of prior briefs. The `prior_briefs` parameter can remain in signatures but always receives `[]` in parallel mode.

**Also update:** `backend/src/v3_blueprint/planning/persistence.py` (~line 295) — resume mirrors the parallel/serial split; update both or resumes diverge from fresh runs.

**Breaks (must update):** `backend/tests/generation/test_stage2_parallel.py` — `test_parallel_stage2_passes_only_anchor_brief_to_non_anchor_sections`, `test_parallel_stage2_fans_out_without_prior_briefs_when_anchor_fails`, `test_parallel_stage2_propagates_anchor_exception`. Replace with: all sections dispatched in one wave; a single section exception is isolated (placeholder brief) and does not fail siblings; plan-derived continuity is present in each user message. Serial-mode test (`test_stage2_uses_serial_invocation_order_when_parallel_flag_is_false`) stays valid.

### A2. Expander reasoning medium → low

`backend/src/v3_execution/config/models.py` line 64: `V3_STAGE2_EXPANDER: "medium"` → `"low"`. Code change (no env exists for per-node reasoning). Guarded rollout in §8 / §9.

### A3. Brief length cap

Two edits. (1) `backend/src/v3_blueprint/planning/section_expander.py` system prompt: add an explicit rule — each component intent is **direction, not content**; max ~80 words; never finished problem text, hint text, option text, or worked solutions; those belong to the writers. (2) `validate_section_brief` (in `backend/src/v3_blueprint/planning/validators.py` or adjacent): reject any component intent over the word cap so attempt 2 retries with the violation named. Add a unit test with an over-long intent fixture.

### A4. Parallel item generation per card

`backend/src/generation/v3_studio/router.py` line ~1051–1060: `for row in cards: results.append(await execute_items(...))` → `asyncio.gather` across cards. Preserve result order by card. One card behaves identically; multi-card lessons stop paying serially.

**Breaks (must update):** any test stubbing `execute_items` sequentially — check `backend/tests/generation/test_v3_item_review.py`.

### A5. Timeout and concurrency env (see §6 for the full table)

240s expander timeout → 100s; section/question writer concurrency 3 → 5.

---

## 3. Workstream B — Merge critic on nominated pairs only

`backend/src/planning/agents.py` → `run_adjacent_merge_critics` currently iterates every adjacent pair. Change: iterate only pairs present in `plan.adjacent_merge_reviews` (the planner's nominations, `backend/src/planning/models.py:73`) plus any lesson with `merge_warning: true` paired with its neighbor. Called from `backend/src/planning/routes.py:309` — call site unchanged.

**Breaks (must update):** `backend/tests/planning/test_path_contracts.py` → `test_merge_critic_runs_for_every_adjacent_pair`. Replace with two tests: critic runs exactly once per nominated pair; critic runs zero times when nominations are empty. Check `backend/tests/planning/test_outcomes.py` / `backend/tests/planning/test_projections.py` for count assumptions on `merge_critic_results`.

**UI consequence:** the "Merge critic — N reviews" panel in `frontend/src/routes/units/[id]/+page.svelte` is deleted. Verdicts surface only as inline questions on the plan (see §7, Screen 3).

---

## 4. Workstream C — Prompt packaging

### Layout

```
backend/resources/prompts/
  manifest.yaml
  constructor.md          editable      NEW (see Workstream D)
  path-planner.md         editable      move of path-planner-v1.txt
  merge-critic.md         editable      move of merge-critic-v1.txt
  structural-planner.md   LOCKED        extract from structural_planner.py f-string
  section-expander.md     editable      extract from section_expander.py f-string
  section-writer.md       editable      extract from v3_execution/prompts/section_writer.py
  question-writer.md      editable      extract from v3_execution/prompts/question_writer.py
  quiz-items.md           LOCKED        extract from v3_execution/prompts/item_prompt.py
```

Source files for extraction / moves:

- `backend/src/planning/` prompt `.txt` files (path-planner-v1, merge-critic-v1) → `.md` under `backend/resources/prompts/`
- `backend/src/v3_blueprint/planning/structural_planner.py` — f-string system prompt → `structural-planner.md`
- `backend/src/v3_blueprint/planning/section_expander.py` — f-string system prompt → `section-expander.md`
- `backend/src/v3_execution/prompts/section_writer.py` → `section-writer.md`
- `backend/src/v3_execution/prompts/question_writer.py` → `question-writer.md`
- `backend/src/v3_execution/prompts/item_prompt.py` → `quiz-items.md`

`manifest.yaml` per entry: `id`, `file`, `stage_label` (teacher-facing, e.g. "Plans your lessons"), `editable: true|false`, `version`.

### Rules

- Extraction is verbatim for the static portion; runtime interpolation (planner index block, component contracts, per-section context) stays in code and is appended to the loaded file text. The file is the *system prompt body*, not the whole assembled prompt.
- Resolution at call time: default file + per-teacher overlay (new DB table `prompt_overrides`: user_id, prompt_id, text, updated_at). Locked prompts never consult overlays.
- Every generation stores the SHA-256 of each effective prompt used (extend `report_json` or trace records). Answerable question: "which prompt wrote this lesson?"
- Loader extends the existing pattern in `backend/src/planning/prompts.py`; add the new names to `_PROMPT_NAMES` equivalent and route stage1/expander/writer builders through it.

**Breaks (must update):** `test_phase5_prompts_are_verbatim` in `backend/tests/planning/test_path_contracts.py` pins prompts to `.txt` names — update paths after the move. `backend/tests/v3_execution/prompts/test_shared_prompt_prefix.py` asserts prompts share `build_v3_shared_prefix` — the shared prefix becomes part of the assembled output around the loaded file; keep the assertion true by prepending the prefix in the loader, and update string-containment tests (`"2-4 misconceptions"` etc.) to read from the file.

### UI: "How lessons get written" (new settings page)

One page listing manifest entries by `stage_label` in pipeline order. Each row expands to the prompt **rendered as formatted markdown** (headings, lists, emphasis — not a raw textarea). Editable prompts get an Edit toggle that swaps rendered view for an editor, with Save and "Reset to default". Locked prompts show a lock and one sentence: "This one keeps the quiz honest, so it can't be changed." Edited prompts display a "modified" badge everywhere they're referenced. Route suggestion: `/settings/prompts` (`frontend/src/routes/settings/prompts/`).

---

## 5. Workstream D — Constructor + readback (Level A rebuild)

### New LLM node

Add `V3_CONSTRUCTOR` to `V3_NODE_SLOTS` (slot: FAST) and `V3_NODE_REASONING` (`"medium"`) in `backend/src/v3_execution/config/models.py`. Also register a timeouts dict entry. Prompt: `constructor.md`. Input: subject, grade, raw teacher text. Output (structured): `destination_objective`, `starting_knowledge[]`, `curriculum_context`, `class_notes` (feeds group setup later), and `clarifying_question: str | null`. Rule in the prompt: ask **at most one** question, only when the raw text is genuinely ambiguous about what is being taught; otherwise draft with stated assumptions.

### Flow

Create-unit form shrinks to subject select, grade select, one free-text box (see §7, Screen 1). Submit → constructor → readback screen (§7, Screen 2). "That's right" → existing `PathPlannerRequest` built from constructor output → existing path planner, validator, nominated-pairs critic. Typed corrections → constructor re-run with the correction appended → readback refreshes. The path planner and everything downstream never know the form changed.

**Deleted:** `destination_objective`, `starting_knowledge`, `curriculum_context` inputs from `frontend/src/routes/units/+page.svelte`. Backend fields stay (constructor fills them). **Check for breakage:** unit-creation route validation that currently requires those fields from the client; `tests/routes` covering unit creation; onboarding flow if it links to the old form.

### Plan editing by chat

On the "Your lessons" screen (`frontend/src/routes/units/[id]/+page.svelte`), a single text input replaces the split/merge/skip/edit forms. Teacher text → LLM patch call (reuse constructor node or a small `plan-editor` prompt) → produces an edited `PathPlan` → **existing** `validate_path_plan` runs → validator failures rendered as plain sentences ("Lesson 4 needs something not yet taught — I've added it as Lesson 3" style). The approval lock conditions (`assert_approvable`) are unchanged. Keep the existing version-on-edit behavior (edits create a new draft path version; undo preserved).

---

## 6. Environment variables

Set these now (all already exist in code):

```
V3_STAGE2_PARALLEL=true                    # confirm, default true
V3_TIMEOUT_STAGE2_SECTION_SECONDS=100      # was 240
V3_CONCURRENCY_SECTION_MAX=5               # was 3
V3_CONCURRENCY_QUESTION_MAX=5              # was 3
V3_CONCURRENCY_VISUAL_MAX=4                # unchanged, listed for completeness
V3_TIMEOUT_SECTION_SECONDS=90              # unchanged
V3_TIMEOUT_QUESTION_SECONDS=60             # unchanged
```

Read sites to confirm: `backend/src/v3_execution/config/timeouts.py`, `backend/src/v3_execution/config/concurrency.py`, `backend/src/v3_blueprint/planning/retry.py`. Mirror values in `backend/.env.example`.

Note: per-node **reasoning levels and slot assignments have no env vars** — they live in `V3_NODE_REASONING` and `V3_NODE_SLOTS` in `backend/src/v3_execution/config/models.py` and change via code (A2 and §6.1). The `V3_FAST/STANDARD/PREMIUM_*` env vars choose which model fills each slot, not which node uses which slot.

### 6.1 Model slot adjustments (code, `models.py`)

| Node | Now | Change to | Rationale / risk |
|---|---|---|---|
| V3_STAGE2_EXPANDER | STANDARD, medium | STANDARD, **low** | A2. After brief cap proves stable, trial FAST as a second step — not both changes at once. |
| V3_QUESTION_WRITER | STANDARD, medium | **FAST, low** | Question wording from a fully specified plan + card is mechanical. Watch distractor quality on first runs. |
| V3_BLUEPRINT_ADJUST | STANDARD, medium | **FAST, medium** | Small targeted edits; low risk. |
| V2_COMPONENT_SELECTOR | STANDARD, medium | leave | Touches plan quality; not worth the savings. |
| V3_SECTION_WRITER | STANDARD, low | leave for now | The main prose quality surface. Trial FAST only after expander changes are validated. |
| V3_ITEM_EXECUTOR | PREMIUM, medium | **leave** | The wall. Never economize here. |
| V3_STAGE1_PLANNER | STANDARD, high | **leave** | Out of scope by decision. |
| V3_CONSTRUCTOR | _(new)_ | FAST, medium | Workstream D. |

---

## 7. UI specification for changed screens

Language rules across all screens: never show *concept path, variant, canonical, skeleton, delta, support level, merge critic, forward verified, prerequisite risk, lesson_mode, misconception count, knowledge type, structural plan, halt*. Use: *your lessons, versions, groups, everyone, same quiz, locked in, needs lesson N first*.

**Screen 1 — New unit.** (`frontend/src/routes/units/+page.svelte`) Subject select, grade select, one large free-text box labeled "What are you teaching? Anything I should know about this class?", one button "Plan it". Nothing else. Empty state copy on the units list changes to match ("Tell me what you're teaching and I'll plan the lessons.").

**Screen 2 — Readback (new).** "Here's my understanding:" followed by two short blocks in plain sentences — "By the end, students can …" and "I'm assuming they already know …" — plus curriculum note if composed. Primary button "That's right". Secondary: an inline text input "type what's off". If the constructor returned a `clarifying_question`, it renders above the blocks as one question with a text input, and the readback fills in after the answer. No JSON, no field names.

**Screen 3 — Your lessons.** (`frontend/src/routes/units/[id]/+page.svelte`) Numbered lesson list; dependency shown as "needs lesson 1", not slugs. Nominated-pair verdicts render inline as one question card: "Lessons 2 and 3 might work as one lesson — keep apart / combine" (two buttons; `teacher_decision` and `merge_suggested` both render this; `keep_separate` renders nothing). One chat input at the bottom for edits. Primary button "Looks good — lock it in", disabled until the same conditions as today's approve gate, with failures shown as sentences. **Removed from this screen:** merge-critic review panel, forward-verified / prerequisite-risk stat blocks, split/merge/skip forms, knowledge-type dropdown.

**Screen 4 — Lesson card (the halt, replaces plan review presentation).** Title; "The one thing this lesson teaches: …" (card objective); "Watch for: …" (misconceptions, plain phrasing, omitted if none). Primary "Make the lesson"; secondary inline input "something off? type it" which patches the plan and re-renders the card. While generating: per-section progress with teacher words ("Writing the opening… writing practice… writing the quick check"), sections streaming in as they finish (the runner already emits `SECTION_READY`).

**Screen 5 — Lesson view.** Rendered lesson; buttons "Print" and "Make versions for my groups". The versions button opens the versions panel: each group as a card — group name in the teacher's own words, one sentence per structural change ("practice stays guided; no solo section"), and a fixed banner "All versions share the same quiz, so you can compare the whole class fairly." Group definitions come from class settings (one free-text description, composed into groups by the constructor node), set once, editable there. **Removed:** variant configuration from the prepare path; `UnitGroupsPanel` checkbox fieldset moves behind this opt-in panel; `LessonShapePanel` mode/misconception controls are removed from teacher view (values inferred; keep an internal/debug flag if needed).

**Settings — "How lessons get written."** Per §4. Route: `/settings/prompts`.

---

## 8. Affected-areas checklist (breakage sweep)

Backend:

- [ ] `retry.py` anchor-serial removal + `persistence.py:295` (mirrors the parallel/serial split for resume — update both or resumes will diverge from fresh runs)
- [ ] `test_stage2_parallel.py` rewritten per A1
- [ ] `run_adjacent_merge_critics` nominated-only + `test_path_contracts.py`, `test_outcomes.py`, `test_projections.py`
- [ ] `validate_section_brief` word cap + fixture test
- [ ] `router.py` item-gather + any test stubbing `execute_items` sequentially (`test_v3_item_review.py`)
- [ ] Prompt extraction: verbatim tests, shared-prefix tests, `_PROMPT_NAMES` set, hash-stamping on generations
- [ ] `prompt_overrides` table migration; overlay resolution in loader; locked-prompt bypass
- [ ] Constructor node registration (`V3_NODE_SLOTS`, `V3_NODE_REASONING`, timeouts dict entry), route, structured output model
- [ ] Unit-creation route: accept raw text payload; keep old payload accepted during transition if anything else posts it
- [ ] Resume paths (`claim_resume_attempt`, `resume_stage2`) still coherent with one-wave fan-out

Frontend:

- [ ] `units/+page.svelte` new create form; `units/[id]/+page.svelte` screens 3–5 rebuild; `page.test.ts` files updated
- [ ] `LessonShapePanel`, `UnitGroupsPanel` re-homed per §7
- [ ] Studio/print/pack pages: sweep `lib/types/units.ts`, `lib/types/v3.ts` and all listed variant-referencing files for banned words in rendered strings (type names may keep `Variant`; user-visible strings may not)
- [ ] Vite manual-chunk list unaffected (templates untouched)

Docs:

- [ ] Mark superseded sections of `handoff/11_UI_AND_FLOWS.md`, `07_DIFFERENTIATION_MODEL.md` (UI portions only), `14_IMPLEMENTATION_PHASES.md` with a pointer to this file. Do not delete them.

---

## 9. Rollout order and acceptance checks

Order: (1) baseline — run one lesson on current settings, keep the `elapsed=` log lines; (2) env changes + A1 + A4; (3) A2 + A3 with side-by-side brief comparison on the same lesson; (4) 6.1 slot changes one at a time; (5) Workstream B; (6) Workstream C; (7) Workstream D + screens.

Accept when all of these hold:

1. Single-version lesson, 5 sections: wall-clock under 5 minutes (baseline logged for comparison).
2. Same-lesson briefs at low reasoning judged equivalent in a side-by-side read; no brief intent over the word cap.
3. No user-visible string contains a banned word from §7.
4. Critic call count equals nominated-pair count on a test path; zero when none nominated.
5. A teacher-edited `section-writer.md` overlay changes output; reset restores default; locked prompts reject edits at the API; every new generation carries prompt hashes.
6. Create-unit → readback → locked plan achievable typing only free text (no deleted form fields anywhere).
7. Full test suite green after the checklist in §8.
8. The wall verified unchanged: item generation reads only card fields (re-run the beta-audit grep for prose leakage into item prompts).

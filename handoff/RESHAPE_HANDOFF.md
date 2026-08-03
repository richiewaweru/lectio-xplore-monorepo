# RESHAPE_HANDOFF.md

**Status:** authoritative. **Supersedes `LANES_HANDOFF.md` entirely** (the writer-queue design in its §5 is abandoned in favour of append-only storage, and the lane step count is now decided by an experiment). Builds on the completed `RESTRUCTURE_HANDOFF.md` wave.

**Branch:** `xplore`. **Date:** 2026-08-03.

---

## 1. What this reshape is

Three changes, in a forced order:

1. **Settle the expander.** Determine by experiment whether the middle LLM call per section (plan → brief → prose) earns its place. Delete it if not.
2. **Append-only step storage.** Replace the mutable `chunked_state` blob with immutable per-step records. This removes the write race by construction — no writer queue, no supervisor, no drain step.
3. **Lanes.** Reorganize stage 2 from phase barriers (all briefs → all prose → all questions) into per-section lanes that run start-to-finish independently, with quiz items alongside and an overlapped tail.

The order is forced because (1) decides how many steps a lane has, which decides what (2) stores, which (3) is built on. Building lanes first and migrating later means touching storage, resume, and lane code twice.

**Target:** single-version 5-section lesson ≤ 3 min wall-clock; first section on screen ≤ 90s.

## 2. Never touch

The wall (items generated from concept-card fields only; `quiz-items.md` locked; premium slot). The halt (no auto-approval; generation starts only after teacher confirmation). One lesson = one concept. Frozen published packs. One shared quiz item set across all versions. No student-facing features.

**Scoped exception to the "don't touch stage 1" rule:** §4.1 adds `VisualStrategySpec` to `SectionPlan`. This is additive schema only — stage 1's prompt philosophy, model slot, and HIGH reasoning stay as they are. No other stage 1 change is in scope.

## 3. Phase 0 — the expander experiment (gates everything)

**Do not start any other phase until the user has answered 0.3.** Phase 4 (small fixes) is the work to do while waiting.

**Background.** Per section the pipeline runs: expander (plan → `SectionBrief`) then writer (brief → prose). The expander's output is `component_id` (copied verbatim from the plan) plus `content_intent`. The suspicion is that `content_intent` is largely a restatement of the plan's `ComponentSlot.purpose` combined with facts already declared in the component registry card (`sectionField`, `cognitiveJob`, `capacity`). If so, the writer can read those directly.

**0.1** Add flag `V3_SKIP_EXPANDER` (default false). When true, the section writer receives, in place of a brief: the `SectionPlan` (role, title, `transition_note`, `card`, and each `ComponentSlot` with slug + purpose) plus that component's registry contract. Build this as a **temporary, reversible branch in the writer input path** — do not delete anything yet.

**0.2** Generate the *same* lesson twice — flag off, then flag on — and save both outputs plus timings to `experiments/expander/`. Use a lesson with at least one practice section and one check section.

**0.3** **STOP. Report to the user and wait.** Present both outputs side by side with a short factual note on: whether the anchor is still used, whether the misconception is still targeted, whether declared exclusions are honoured, whether difficulty progression is intact, and the timing difference. Do not judge quality yourself — this is the user's call. Post the report in `RESTRUCTURE_PROGRESS.md` under `## AWAITING DECISION: expander`.

**0.4** If the user asks for more evidence, repeat on a second lesson of a different type (a maths procedure rather than a science concept).

**Branching:**

- **Expander dies** → proceed to Phase 1 as written; lanes are 2-step (`prose`, `questions`).
- **Expander lives** → skip Phase 1 entirely, remove the `V3_SKIP_EXPANDER` branch, keep `section-expander.md` and `SectionBrief`; lanes are 3-step (`brief`, `prose`, `questions`); Phases 2–5 proceed unchanged. Record the decision and stop treating the expander as provisional.

## 4. Phase 1 — remove the expander (only if it dies)

**4.1 Rehome the visual strategy — required, do this first.** `VisualStrategySpec` (subject, visual_job, type_hint) is currently produced *only* by the expander, and the assembler reads it at `assembler.py:199-205`. Deleting the brief orphans it. Move it onto `SectionPlan` as an optional field, populated by stage 1 when `visual_required` is true (stage 1 already decides `visual_required`, so it has the context). Update `structural-planner.md` minimally to describe the new field, the plan validator to require it when `visual_required`, and the assembler to read it from the plan. Verify a visual-bearing lesson still renders its diagram before continuing.

**4.2 Rewrite `section-writer.md`** to consume plan section + component slug/purpose + registry contract. The consolidation the brief used to perform now happens in the prompt template: render constraints as a structured list (component purpose, capacity limits, anchor, misconception, exclusions, transition note), not as prose. Follow §6.2 — this is the moment not to reintroduce a stringify habit.

**4.3 Assembler:** build `ComponentPlan.content_intent` from the plan's `purpose` + contract rather than `comp_brief.content_intent` (`assembler.py:72-83`). Keep `ComponentPlan`'s shape so downstream consumers are unaffected.

**4.4 Delete**, in this order, running tests between each: `section_expander.py`; `SectionBrief` / `ComponentBrief` models; `validate_section_brief` and the advisory word cap; `section-expander.md` and its manifest entry; the expander's slot/reasoning/timeout entries; brief-related resume state. Then clean the consumers: `retry.py`, `persistence.py`, `validators.py`, `assembler.py`, `dtos.py`, `router.py`, and **`block_generate_routes.py`** (see §7 — do Phase 4.1 before this).

## 5. Phase 2 — append-only step storage

**5.1 New table `generation_steps`:**

```
generation_id  (fk)
part_id        str   # a section today; deliberately NOT named section_id
variant_id     str   # "everyone" for single-version lessons
step           str   # "prose" | "questions" | ("brief" if expander lived)
kind           str   # what this generation produces, e.g. "lesson"
payload        json  # opaque — the step's output
created_at     ts
unique(generation_id, part_id, variant_id, step)
index(generation_id)
```

**Key names must stay generic.** `part_id`/`variant_id`/`step`/`kind` — never `section_id`. This is what keeps the storage usable when the lesson spec changes or another resource type is added; a future unit-level or worksheet generation reuses the table unchanged. Payload is opaque JSON and must never be given a lesson-specific schema at the storage layer.

**5.2 `fold(rows) -> state`** produces the shape today's code expects. Add a comment at the fold explaining *why* state is computed rather than stored, so nobody reintroduces a cached mutable copy and brings the race back.

**5.3** Replace every stage-2 `persist_chunked_state` write with a row insert, and every read with `fold()`. Deleted concepts: writer queue, supervisor, restart semantics, drain-before-tail, kill-the-writer test, simultaneous-write race test. Simultaneous inserts are ordinary database behaviour and need no coordination.

**5.4 Resume** becomes "which `(part, variant, step)` rows exist for this generation? rebuild only what's missing." A crash after prose re-runs only questions for that part. Migration must not orphan in-flight generations — if any exist, either drain them or backfill rows from the existing blob; state that choice in the progress file.

## 6. Phase 3 — lanes

**6.1** Ship the items/lane overlap first as a standalone change: `gather(items_job, stage2)` instead of sequential. Two lines, no new concepts, proves independence on a live run. Legality: items read only card fields; lanes read only the approved plan; continuity comes from `transition_note` (established in A1), so no lane reads a sibling's output.

**6.2 `run_lane(part_id, variant_id)`** in a new `v3_execution/runtime/lanes.py`: steps sequential inside a lane, lanes parallel outside. After each step: insert a row, emit a progress event. After the final step: validate, emit `SECTION_READY`. Per-step retry policy unchanged; a step failing after retries parks the lane as `failed(step)` without affecting siblings (`ship_with_holes` still applies).

**6.3** Pipeline: `gather(items, *lanes, return_exceptions=True)` → tail `gather(coherence, answer_key)` → assembly. Verify the answer key reads questions from state rather than from coherence output before overlapping them.

**6.4 Lane budget:** wrap each lane in `asyncio.timeout(V3_LANE_BUDGET_SECONDS)`, default 240. On expiry cancel cleanly, record `failed(budget)` with the step it died in, continue. This prevents one pathological lane from defining the whole generation.

**6.5 Visuals patch in.** A lane emits `SECTION_READY` *without* its visual and enqueues a visual job; visuals run concurrently under the existing executor and `V3_CONCURRENCY_VISUAL_MAX`, outside lane budgets. On completion, insert a `visual` row and emit an event; the frontend patches the section in place. The tail does not wait for visuals; late visuals still patch into the stored document.

**6.6 `runner.py` shrinks:** section/question scheduling moves into lanes; it keeps visuals coordination, tail, assembly. Delete dead scheduling paths rather than leaving them. The serial `V3_STAGE2_PARALLEL=false` mode becomes "lane concurrency = 1", not a separate code path — grep for dependents first.

**6.7 Env:** add `V3_LANE_BUDGET_SECONDS=240`, `V3_CONCURRENCY_LANE_MAX=6`; retire `V3_CONCURRENCY_SECTION_MAX` and `V3_CONCURRENCY_QUESTION_MAX` from the lane path. Update `.env.example`, log resolved values at pipeline start, and list in the progress file which variables the user must set on Railway.

## 7. Phase 4 — small fixes (do these while Phase 0 awaits a decision)

**7.1 Teacher corrections as typed data.** `router.py:3577` and `:3609` append corrections onto `content_intent` as free text. Replace with `corrections: list[Correction]` where `Correction = {text, created_at, applied_in_generation}`; the writer prompt renders them in a dedicated section. This currently contradicts the project's "teacher edits are sacred" commitment — a concatenated correction cannot be counted, displayed, removed, or verified. **Do this before §4.4**, because it touches `block_generate_routes.py`, the same single-block regeneration path the expander removal rewrites.

**7.2 Type at the seam.** `preview_mapper.py:57` (`"; ".join(content_intent)`) and `assembler.py:204-205` (`", ".join(must_show/must_not_show)`) stringify structured data that consumers must re-read. Rule: structured data crosses module boundaries structured; flattening happens only in the prompt template, at the last moment. Fix these two; apply the rule opportunistically elsewhere as files are touched. Do not undertake a codebase-wide sweep.

**7.3 Groups-tab copy.** Leftover from the previous wave's banned-word sweep: `UnitGroupsPanel` still renders "Canonical structure; no support toggles", "{support_level} support", "No differentiated groups… canonical core shape"; `ResourceComposerPanel` renders "Canonical source only." These are teacher-reachable tabs, not debug. Use: "Everyone", plain sentences, "No groups yet — describe your class and I'll set them up."

## 8. Phase 5 — later, not now

**8.1** Skeleton by lookup: derive the role sequence from `skeletons.yaml` (`knowledge_type` + mode) instead of having stage 1 generate roles that `validate_structural_plan_roles` then grades against the same file. Deletes that validator entirely. Natural to pair with §4.1 since both are stage 1 schema work — but out of scope for this wave.

**8.2** Diff-aware variant fan-out: variants already inherit canonical cards and `lesson_intent` (`_variant_plan_for_fanout`), but each still runs a full stage 2. Sections unchanged by a variant's declared delta should reuse canonical prose by reference; only delta-touched sections regenerate. Safe because of the one-variable-per-variant rule. Wait for real teacher usage of versions.

## 9. Acceptance

1. Phase 0 report delivered and a decision recorded before any Phase 1–3 work.
2. If the expander was removed: a visual-bearing lesson still renders its diagram; no `SectionBrief` reference remains; single-block regeneration still works.
3. Simultaneous lane completion loses nothing (two lanes finishing in the same instant produce two rows).
4. Mid-lane resume verified: no completed step ever re-runs.
5. One deliberately failed lane → lesson ships with one marked gap, siblings intact; a stalled lane parks at the budget while siblings complete.
6. First `SECTION_READY` ≤ 90s; full single-version 5-section lesson ≤ 3 min on a live run, with log evidence.
7. `SECTION_READY` precedes `visual_ready` for visual sections; coherence and answer key overlap in the logs.
8. Wall re-audit: item generation reads only card fields — re-run the grep, record the output.
9. Corrections are countable and removable, not concatenated prose.
10. No banned words in teacher-reachable copy (§7.3 sites included).
11. Full backend + frontend suites green.

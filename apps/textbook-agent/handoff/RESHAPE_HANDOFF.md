# RESHAPE_HANDOFF.md (v2 — post-decision)

**Status:** authoritative. Supersedes `LANES_HANDOFF.md` (its writer-queue design is abandoned) and replaces v1 of this file. Builds on the completed `RESTRUCTURE_HANDOFF.md` wave.

**Branch:** `xplore`. **Date:** 2026-08-03.

---

## 1. Decision record — the expander lives

Three rounds of testing settled this. It is closed; reopening requires new evidence, not new argument.

- **Round 1** (skip vs keep, unmodified writer prompt): skip arm lost the anchor in 3 of 5 sections and dropped a misconception from `apply`. Suggested the expander did real consolidation work.
- **Round 2** (fair retest — writer prompt rewritten to render anchor / misconceptions / exclusions / role / transition as explicit structured constraints, and `anchor.example` plumbed through blueprint → work order where it had previously been dropped): skip arm reached 5/5 anchor coverage and recovered the `apply` misconception, matching both expander arms. **Quality: equal.**
- **Round 3** (six interleaved runs, three per arm, identical fixed plan): median totals 191.1s with expander vs 211.9s without. Delta 20.8s against arm spreads of 58.3s and 262.8s. Per-section medians mixed — skip slower in 3 of 5 sections, faster in 2 — not the uniform slowdown a real prompt-size penalty would produce. One 280.9s outlier on a skip `model` writer (6× that arm's other runs) is provider tail latency, not prompt cost. **Speed: unresolved; neither arm demonstrably faster.**

**Decision:** keep the expander. Quality was equal, speed was not separable, and the working configuration carries less change risk.

**Consequences:**

- `V3_SKIP_EXPANDER` is removed. `section_expander.py`, `SectionBrief` / `ComponentBrief`, `validate_section_brief`, the advisory brief cap, and `section-expander.md` all stay.
- **Phase 1 of v1 (expander removal) is deleted from this plan.** `VisualStrategySpec` stays inside `SectionBrief`; no rehome is needed.
- **Stage 1 is now fully untouched** — the scoped exception in v1 §2 no longer applies.
- Lanes are **3-step**: `brief → prose → questions`. Storage stores three step types per part.

**Kept from the experiment rounds** (independent of the decision, do not revert): the improved `section-writer.md` structured constraints, and the `anchor.example` plumbing fix through blueprint → work order.

## 2. What this reshape now is

Two changes, in order:

1. **Append-only step storage** — replace the mutable `chunked_state` blob with immutable per-step records. Removes the write race by construction: no writer queue, no supervisor, no drain step.
2. **Lanes** — reorganize stage 2 from phase barriers (all briefs → all prose → all questions) into per-section lanes running start-to-finish independently, with quiz items alongside and an overlapped tail.

Storage precedes lanes so lanes are built on final storage rather than migrated onto it.

**Target:** single-version 5-section lesson ≤ 3 min wall-clock; first section on screen ≤ 90s.

## 3. Never touch

The wall (items generated from concept-card fields only; `quiz-items.md` locked; premium slot). The halt (no auto-approval; generation starts only after teacher confirmation). One lesson = one concept. Frozen published packs. One shared quiz item set across all versions. **Stage 1 planner** — prompt, schema, slot, reasoning; no exceptions in this wave. No student-facing features.

## 4. Phase 1 — append-only step storage

**4.1 New table `generation_steps`:**

```
generation_id  (fk)
part_id        str   # a section today; deliberately NOT named section_id
variant_id     str   # "everyone" for single-version lessons
step           str   # "brief" | "prose" | "questions"
kind           str   # what this generation produces, e.g. "lesson"
payload        json  # opaque — the step's output
created_at     ts
unique(generation_id, part_id, variant_id, step)
index(generation_id)
```

**Key names are load-bearing.** `part_id` / `variant_id` / `step` / `kind` — never `section_id`. This is what lets the table survive a lesson-spec change or a new resource type. The payload column stays opaque JSON and must never be given a lesson-specific schema at the storage layer.

**4.2 `fold(rows) -> state`** produces the shape today's code expects. Add a comment at the fold explaining *why* state is computed rather than stored, so nobody reintroduces a cached mutable copy and brings the race back.

**4.3** Replace every stage-2 `persist_chunked_state` write with a row insert and every read with `fold()`. Deleted concepts: writer queue, supervisor, restart semantics, drain-before-tail, kill-the-writer test, simultaneous-write race test. Simultaneous inserts are ordinary database behaviour and need no coordination.

**4.4 Resume** becomes "which `(part, variant, step)` rows exist? rebuild only what's missing." A crash after prose re-runs only questions for that part. The migration must not orphan in-flight generations — drain them or backfill rows from the existing blob; state which was chosen and why.

## 5. Phase 2 — lanes

**5.1** Ship the items/lane overlap first, standalone: `gather(items_job, stage2)` instead of sequential. Two lines, no new concepts, proves independence on a live run. Legality: items read only card fields; lanes read only the approved plan; continuity comes from `transition_note` (established in A1 of the previous wave), so no lane reads a sibling's output.

**5.2 `run_lane(part_id, variant_id)`** in a new `v3_execution/runtime/lanes.py`: steps sequential inside a lane (`brief → prose → questions`), lanes parallel outside. After each step: insert a row, emit a progress event. After the final step: validate, emit `SECTION_READY`. Per-step retry policy unchanged; a step failing after retries parks the lane as `failed(step)` without affecting siblings (`ship_with_holes` still applies).

**5.3** Pipeline: `gather(items, *lanes, return_exceptions=True)` → tail `gather(coherence, answer_key)` → assembly. Verify the answer key reads questions from state rather than from coherence output before overlapping them.

**5.4 Lane budget:** wrap each lane in `asyncio.timeout(V3_LANE_BUDGET_SECONDS)`, default 240. On expiry cancel cleanly, record `failed(budget)` with the step it died in, continue. Round 3 produced a 280.9s single-call stall, so this is not hypothetical — the budget is what keeps one provider tail event from defining the whole generation.

**5.5 Visuals patch in.** A lane emits `SECTION_READY` *without* its visual and enqueues a visual job; visuals run concurrently under the existing executor and `V3_CONCURRENCY_VISUAL_MAX`, outside lane budgets. On completion, insert a `visual` row and emit an event; the frontend patches the section in place. The tail does not wait for visuals; late visuals still patch into the stored document.

**5.6 `runner.py` shrinks:** section/question scheduling moves into lanes; it keeps visuals coordination, tail, assembly. Delete dead scheduling paths rather than leaving them. The serial `V3_STAGE2_PARALLEL=false` mode becomes "lane concurrency = 1", not a separate code path — grep for dependents first.

**5.7 Env:** add `V3_LANE_BUDGET_SECONDS=240`, `V3_CONCURRENCY_LANE_MAX=6`; retire `V3_CONCURRENCY_SECTION_MAX` and `V3_CONCURRENCY_QUESTION_MAX` from the lane path. Update `.env.example`, log resolved values at pipeline start, and list in the progress file which variables the user must set on Railway.

## 6. Already landed (previous session, do not redo)

- Corrections as typed data (`corrections: list[Correction]`) replacing string concatenation onto `content_intent`.
- Type-at-the-seam fixes at `preview_mapper.py:57` and `assembler.py:204-205`.
- Groups-tab copy sweep (`UnitGroupsPanel`, `ResourceComposerPanel`).

## 7. Later, not now

**7.1 Skeleton by lookup.** Derive the role sequence from `skeletons.yaml` (`knowledge_type` + mode) instead of having stage 1 generate roles that `validate_structural_plan_roles` then grades against the same file. Deletes that validator entirely and makes the open `build`-role defect (§8) structurally impossible. Touches stage 1 schema — out of scope this wave.

**7.2 Diff-aware variant fan-out.** Variants already inherit canonical cards and `lesson_intent` (`_variant_plan_for_fanout`), but each still runs a full stage 2. Sections unchanged by a variant's declared delta should reuse canonical prose by reference; only delta-touched sections regenerate. Safe because of the one-variable-per-variant rule. Wait for real teacher usage of versions.

## 8. Known defects (open, not in scope)

**`build` role.** A live stage 1 run during round 1 emitted a section role `build` that is not a slot in `skeletons.yaml`, failing skeleton role validation — the experiment used a fixed plan as a result. Real defect in the current planner/skeleton pairing. Fix belongs with §7.1.

## 9. Acceptance

1. `V3_SKIP_EXPANDER` removed; no dead skip-branch code remains; the round-2 writer-prompt and `anchor.example` improvements are still in place.
2. Simultaneous lane completion loses nothing (two lanes finishing in the same instant produce two rows).
3. Mid-lane resume verified: no completed step ever re-runs; a crash after prose re-runs only questions.
4. Migration orphans no in-flight generation.
5. One deliberately failed lane → lesson ships with one marked gap, siblings intact; a stalled lane parks at the budget while siblings complete.
6. First `SECTION_READY` ≤ 90s; full single-version 5-section lesson ≤ 3 min on a live run, with log evidence.
7. `SECTION_READY` precedes `visual_ready` for visual sections; coherence and answer key overlap in the logs.
8. Wall re-audit: item generation reads only card fields — re-run the grep, record the output.
9. Storage keys are generic (`part_id`, `variant_id`, `step`, `kind`); payload carries no lesson-specific schema.
10. Full backend + frontend suites green.

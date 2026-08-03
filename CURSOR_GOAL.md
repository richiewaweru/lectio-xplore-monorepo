# CURSOR_GOAL.md — The reshape (post-decision)

You are running a long implementation session on the `xplore` branch of `text-book-generator`. Your source of truth is `handoff/RESHAPE_HANDOFF.md` (v2, post-decision). Read it fully before writing any code.

**Two files in `handoff/` are dead — ignore both:** `LANES_HANDOFF.md` (its writer-queue design was abandoned in favour of append-only storage) and any v1 copy of the reshape handoff (its Phase 1 removed the expander, which was subsequently kept). If you find guidance in either that conflicts with v2, v2 wins.

The user is not watching continuously. Work carefully rather than quickly. There is no experiment phase in this session — the decision is made — so this is a straight implementation run.

---

## 1. The decision that shapes this session

**The expander lives.** Settled by three rounds of testing (recorded in handoff §1): quality was equal between arms, speed was not separable, so the working configuration was kept.

Concretely this means:

- Remove the `V3_SKIP_EXPANDER` flag and its branch. No dead skip-path code.
- Keep `section_expander.py`, `SectionBrief` / `ComponentBrief`, `validate_section_brief`, the advisory brief cap, and `section-expander.md`.
- **Do not** rehome `VisualStrategySpec` — it stays inside `SectionBrief`.
- **Stage 1 is entirely untouched this wave.** The scoped exception that existed in the earlier draft no longer applies.
- Lanes are **3-step**: `brief → prose → questions`. Storage stores three step types per part.

**Do not revert two things the experiment rounds produced**, which stand on their own merits: the improved structured constraints in `section-writer.md`, and the `anchor.example` plumbing through blueprint → work order (it was previously being dropped in transit — a real bug).

## 2. Fidelity rules

- **Never touch** the wall, the halt, one-lesson-one-concept, frozen packs, the shared quiz set, or stage 1.
- **Do not improvise scope.** If a change seems to require something not in the handoff, stop and record it (§5) rather than deciding.
- **No refactors, renames, or cleanups outside the handoff**, however tempting.
- **Storage key names are load-bearing:** `part_id`, `variant_id`, `step`, `kind`. Never `section_id`. The payload column stays opaque JSON with no lesson-specific schema. This is what makes the storage survive a spec change; a reviewer will check it.
- **One coherent change per commit**, message referencing the handoff section (e.g. `4.1: add generation_steps table`). Tests updated in the same commit as the behavior they cover. Never delete a failing test to go green — rewrite it to assert the new intended behavior.
- Maintain `RESTRUCTURE_PROGRESS.md`: one entry per commit (what changed, files, test evidence, anything deferred). This is the user's only window into the session.
- Handoff §6 lists work already landed in a previous session — do not redo it.

## 3. Order of work

Handoff §4 (storage) → §5 (lanes), in that order. Storage precedes lanes so lanes are built on final storage rather than migrated onto it.

Within §5, ship 5.1 (items overlap) standalone first — it is two lines and proves lane independence on a live run before anything is built on that assumption.

The `V3_SKIP_EXPANDER` removal can land first as a small cleanup commit.

## 4. Verification per phase (mandatory before moving on)

- **Storage:** two rows written in the same instant both survive (this is the race the abandoned queue design existed to prevent — prove it is gone by construction); resume rebuilds only missing steps; the migration orphans no in-flight generation (drain or backfill — state which you chose and why).
- **Lanes:** a deliberately failed lane → lesson ships with one marked gap, siblings intact; a stalled lane parks at the budget while siblings finish; `SECTION_READY` precedes `visual_ready`; coherence and answer key overlap in logs.
- **Every phase:** full backend and frontend suites, not just touched files. Record counts in the progress file. A green targeted test with a red suite means stop and fix.
- **Always last:** wall re-audit — grep that item generation reads only concept-card fields; record the command and its output.

Timing acceptance (≤3 min total, first section ≤90s) requires a live run. Note that observed per-call latency is highly variable — one round-3 writer call took 280s against a ~45s median for the same section — so report the numbers you measure and do not average away outliers silently. If you cannot reach a live environment, say so plainly in the progress file and leave those checks unticked for the user.

## 5. Stop conditions — record and halt, never improvise

- A change appears to require touching the wall, the halt, or stage 1.
- The storage migration would orphan or corrupt existing generations and neither draining nor backfilling is safe.
- Anything that would require a lesson-specific schema in the `payload` column or a lesson-specific storage key.
- Removing the `V3_SKIP_EXPANDER` branch turns out to entangle code paths the handoff does not describe.

For any stop: write the situation, the options you see, and your recommendation into `RESTRUCTURE_PROGRESS.md` under `## BLOCKED`, commit, halt that track, and continue with an independent one if any remains.

## 6. Done

All ten acceptance checks in handoff §9 evidenced in `RESTRUCTURE_PROGRESS.md`; both suites green; `.env.example` updated with the new lane variables and the retired ones removed; `LANES_HANDOFF.md` and any v1 reshape draft marked superseded with a pointer to the current handoff. Finish with a summary: what shipped, what was deferred and why, and before/after timing numbers.

The open `build`-role defect (handoff §8) stays open and out of scope — do not fix it, and do not let it disappear from `## KNOWN DEFECTS`.

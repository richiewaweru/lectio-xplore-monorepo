# CURSOR_GOAL.md — The reshape

You are running a long implementation session on the `xplore` branch of `text-book-generator`. Your source of truth is `handoff/RESHAPE_HANDOFF.md`. Read it fully before writing any code. It **supersedes `LANES_HANDOFF.md`** — ignore that file entirely; its writer-queue design was abandoned. Where the handoff and existing code disagree, the handoff wins; that is the point of the reshape.

The user is not watching continuously. Work carefully rather than quickly. There is exactly one place where you must stop and wait for a human (Phase 0.3) — respect it absolutely.

---

## 1. The one hard stop

**Phase 0 gates everything.** The expander experiment decides whether a lane has two steps or three, which decides what the storage table stores, which the lanes are built on. Building Phases 1–3 before the user has answered means rework of storage, resume, and lane code.

So: run Phase 0.1 and 0.2, write the report per 0.3 into `RESTRUCTURE_PROGRESS.md` under `## AWAITING DECISION: expander`, commit, and **stop that track**. Do not decide the quality question yourself — you may state factual observations (anchor present/absent, exclusions honoured/violated, timings) but the judgement is the user's.

While waiting, do **Phase 4** (§7 of the handoff: corrections as typed data, type-at-the-seam, groups-tab copy). That work is independent and useful under either branch.

If the user's answer is "expander lives": skip Phase 1, remove the `V3_SKIP_EXPANDER` branch, make lanes 3-step, and continue with Phases 2–5 unchanged.

## 2. Fidelity rules

- **Never touch** the wall, the halt, one-lesson-one-concept, frozen packs, or the shared quiz set. The single permitted stage 1 change is the additive `VisualStrategySpec` field in §4.1 — nothing else in stage 1, including its prompt philosophy, slot, or reasoning level.
- **Do not improvise scope.** If a change seems to require something not in the handoff, stop and record it (§5) rather than deciding.
- **No refactors, renames, or cleanups outside the handoff**, however tempting.
- **Storage key names are load-bearing:** `part_id`, `variant_id`, `step`, `kind`. Never `section_id`. The payload column stays opaque JSON with no lesson-specific schema. This is what makes the storage survive a spec change; a reviewer will check it.
- **One coherent change per commit**, message referencing the handoff section (e.g. `5.1: add generation_steps table`). Tests updated in the same commit as the behavior they cover. Never delete a failing test to go green — rewrite it to assert the new intended behavior.
- Maintain `RESTRUCTURE_PROGRESS.md`: one entry per commit (what changed, files, test evidence, anything deferred). This is the user's only window into the session.

## 3. Order of work

Handoff §3 → §7 (while blocked) → §4 → §5 → §6 → acceptance sweep (§9). Within Phase 3, ship §6.1 (items overlap) standalone first — it is two lines and proves lane independence on a live run before anything is built on the assumption.

Two ordering traps called out in the handoff, both easy to get wrong:

- **§7.1 (corrections) must land before §4.4 (expander deletion)** — both rewrite `block_generate_routes.py`, and doing it in the other order means touching that path twice.
- **§4.1 (rehome VisualStrategySpec) must land before any other Phase 1 deletion** — the visual strategy exists only inside `SectionBrief` today (`assembler.py:199-205`); delete the brief first and diagrams break silently. Verify a visual-bearing lesson renders before continuing.

## 4. Verification per phase (mandatory before moving on)

- **Phase 1:** a visual-bearing lesson renders its diagram; no `SectionBrief` reference remains anywhere; single-block regeneration still works end to end.
- **Phase 2:** two rows written in the same instant both survive (this is the race the old design needed a queue for — prove it's gone); resume rebuilds only missing steps; migration does not orphan in-flight generations (drain or backfill — state which you chose and why).
- **Phase 3:** deliberately failed lane → lesson ships with one marked gap, siblings intact; stalled lane parks at the budget while siblings finish; `SECTION_READY` precedes `visual_ready`; coherence and answer key overlap in logs.
- **Every phase:** full backend and frontend suites, not just touched files. Record counts in the progress file. A green targeted test with a red suite means stop and fix.
- **Always last:** wall re-audit — grep that item generation reads only concept-card fields; record the command and its output.

Timing acceptance (≤3 min total, first section ≤90s) requires a live run. If you cannot reach a live environment, say so plainly in the progress file rather than inferring the numbers; leave those checks unticked for the user.

## 5. Stop conditions — record and halt, never improvise

- A change appears to require touching the wall, the halt, or stage 1 beyond §4.1.
- The visual strategy cannot be cleanly rehomed onto `SectionPlan`.
- The storage migration would orphan or corrupt existing generations and neither draining nor backfilling is safe.
- Removing the expander breaks single-block regeneration in a way §4.3 doesn't cover.
- Anything that would require a lesson-specific schema in the `payload` column or a lesson-specific storage key.

For any stop: write the situation, the options you see, and your recommendation into `RESTRUCTURE_PROGRESS.md` under `## BLOCKED`, commit, halt that track, and continue with an independent one if any remains.

## 6. Done

All eleven acceptance checks in handoff §9 evidenced in `RESTRUCTURE_PROGRESS.md`; both suites green; `.env.example` updated with the new lane variables and the retired ones removed; `LANES_HANDOFF.md` marked superseded with a pointer to `RESHAPE_HANDOFF.md`. Finish with a summary: what shipped, what was deferred and why, the expander decision and its evidence, and before/after timing numbers.

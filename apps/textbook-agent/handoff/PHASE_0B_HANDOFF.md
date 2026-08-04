# PHASE_0B_HANDOFF.md — the fair expander test

**Status:** authoritative for this round. Extends Phase 0 of `RESHAPE_HANDOFF.md`. Phases 1–3 remain halted until the user answers §5.

**Branch:** `xplore`. **Date:** 2026-08-03.

---

## 1. Why there is a second round

Phase 0 compared two arms, but only one of them had a prompt written for the job it was doing. In the skip arm the writer received plan purposes plus registry contracts — and was never instructed to carry the anchor into every section or to target the section's misconception. The observed losses (anchor in 2 of 5 sections rather than 5 of 5; misconception absent from `apply`) are therefore consistent with **two different explanations**, and the first round cannot distinguish them:

- **(a)** the expander performs real consolidation the writer cannot do from raw inputs, or
- **(b)** the writer was simply never told to do it.

This round rewrites the writer prompt so the skip arm is actually asked to do the job, then re-runs. That isolates (a) from (b).

Note the timing result is not decisive either way: of the 45s delta, only 27s is the expander itself, and under lanes that cost is per-lane and parallel. Speed is not the deciding factor; lesson coherence is.

## 2. Scope

**In scope:** rewriting `section-writer.md` per §4.2 of the reshape handoff; re-running the skip arm on the identical fixed plan; producing a comparison report.

**Out of scope:** deleting anything; touching `SectionBrief`, `section_expander.py`, storage, or lanes. `V3_SKIP_EXPANDER` stays a flag. No stage 1 changes (see §6 for the bug found, which is recorded but not fixed here).

**Never touch:** the wall, the halt, one lesson = one concept, frozen packs, shared quiz across versions.

## 3. The work

**3.1 Rewrite `section-writer.md`.** The prompt must render, as explicit structured constraints (a list, not prose):

- **Anchor** — the lesson's anchor, with an instruction to use it in *this* section, unless the section's purpose explicitly calls for a fresh context. This is the specific gap the first round exposed.
- **Misconception(s)** this section is meant to surface or correct, named, with the instruction to target them here.
- **Exclusions** — what must not be taught or introduced in this section.
- **Component purpose** for each slot, plus the component's registry contract (`sectionField`, `cognitiveJob`, `capacity` limits).
- **Role and transition note** — where this section sits in the arc and what it hands to the next.

Follow the type-at-the-seam rule (§7.2 of the reshape handoff): these arrive as structured data and are flattened only here, in the template, as a list. Do not concatenate them into a prose paragraph — that would rebuild the expander inside the prompt and defeat the test.

**3.2 Re-run the skip arm** with `V3_SKIP_EXPANDER=true` on the **identical fixed plan** from round one (`experiments/expander/shared_plan.json`). Same harness, same sections. Save to `experiments/expander/skip_expander_v2/`.

**3.3 Re-run the with_expander arm once** on the same plan for a fresh timing baseline (writer-time variance across runs was part of the first round's 45s delta, and the prompt has changed, so the old numbers are no longer comparable).

**3.4 Produce `factual_compare_v2.json`** with the same checks as round one, three arms side by side (with_expander round 1, with_expander round 2, skip_expander v2):

- anchor string-match per section (the headline number: how many of 5)
- misconception mention per section, per misconception id
- exclusion violations per section
- role order preserved, failed sections
- stage 2 and writer timings

## 4. What decides it

**The primary signal is anchor propagation.** Round one: 2 of 5 sections in the skip arm, 5 of 5 with the expander.

- Skip arm now reaches **5 of 5** (or matches the expander arm) → explanation (b). The writer can do the job when asked; the expander was a middleman. **It dies.**
- Skip arm still falls short after being explicitly instructed → explanation (a). The expander performs consolidation that a per-section prompt cannot replicate. **It lives**, permanently — remove `V3_SKIP_EXPANDER`, take 3-step lanes, and stop treating it as provisional.

Secondary signal, same logic: the `apply` section's misconception targeting.

If the result is mixed — anchor recovers but misconceptions don't, or vice versa — report it plainly and recommend **expander lives**. A partial recovery means the writer needs help consolidating, which is the expander's whole justification.

## 5. Reporting and the stop

Write the report into `RESTRUCTURE_PROGRESS.md` under `## AWAITING DECISION: expander (round 2)`: the three-arm table, the anchor count per arm, misconception coverage, timings, and a factual statement of which explanation the numbers support. **Do not judge lesson quality and do not proceed to Phases 1–3.** The decision is the user's. Commit and halt this track.

Prose quality remains the user's read: keep both `skip_expander_v2` and the round-two `with_expander` outputs readable side by side for a human, not only as JSON diffs.

## 6. Recorded separately — a real bug, not fixed here

Round one's live stage 1 run failed skeleton role validation: the planner emitted a role `build` that is not a slot in `skeletons.yaml`, which is why a fixed plan was substituted. This is a genuine defect in the current planner/skeleton pairing and it is exactly the failure class that §8.1 of the reshape handoff (derive the role sequence from `skeletons.yaml` by lookup rather than having stage 1 generate roles) makes structurally impossible.

Record it in `RESTRUCTURE_PROGRESS.md` under `## KNOWN DEFECTS` with the failing plan attached. Do not fix it in this round — it touches stage 1 schema and belongs with the §8.1 work.

## 7. Stop conditions

- The rewritten prompt cannot express a constraint without concatenating it into prose (report; do not improvise a workaround that reintroduces a brief).
- The fixed plan from round one is unavailable or does not reproduce (report; do not substitute a different lesson, which would make the rounds incomparable).
- Any change appears to require touching the wall, the halt, or stage 1.

Record under `## BLOCKED`, commit, halt.

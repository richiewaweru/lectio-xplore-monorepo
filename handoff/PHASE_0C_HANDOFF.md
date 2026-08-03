# PHASE_0C_HANDOFF.md — timing repeat

**Status:** authoritative for this round. Extends Phase 0 / 0B of `RESHAPE_HANDOFF.md`. Phases 1–3 remain halted until the user records a decision.

**Branch:** `xplore`. **Date:** 2026-08-03.

---

## 1. Why a third round

Round 2 settled the quality question: with a properly instructed writer, the skip arm matched the expander arm on anchor coverage (5/5) and misconception targeting. That hypothesis is closed and is **not** re-tested here.

Round 2 left the timing question open, and pointed the opposite way to expectation:

```
                      stage 2    writers    total
 with_expander (r1)   27.2s      177.5s     204.7s
 with_expander (v2)   27.4s      131.5s     158.9s
 skip_expander (v2)    0.0s      207.6s     207.6s
```

Removing a 27-second stage made the run ~49s **slower**. Two explanations, indistinguishable at n=1:

- **(a) Noise.** The same with_expander arm varied by 46s between rounds (177.5 → 131.5) on an identical plan. That variance is larger than the effect being measured, so all three totals may be one number with jitter.
- **(b) Real.** The skip writer now carries a much larger prompt (anchor, misconceptions, exclusions, role, transition, purposes, registry contracts) and performs the consolidation the expander used to do — in the same call that writes prose. If so, the expander was not extra work; it was work moved to a cheaper, parallelisable call.

This round measures which. It is a measurement round only.

## 2. Scope

**In scope:** repeated runs of both arms on the identical fixed plan; a median-based comparison.

**Out of scope:** any code change, prompt change, deletion, or refactor. `section-writer.md` stays exactly as round 2 left it — changing it would invalidate comparison with round 2. No stage 1 changes. No lanes, no storage work.

**Never touch:** the wall, the halt, one lesson = one concept, frozen packs, shared quiz across versions.

## 3. The runs

**3.1** Using `experiments/expander/shared_plan.json` (the same fixed plan as rounds 1 and 2), run:

- `with_expander`: **3 runs**
- `skip_expander`: **3 runs**

Interleave them (with, skip, with, skip, with, skip) rather than running each arm in a block, so provider-side load drifts affect both arms equally. Record the wall-clock start time of each run.

**3.2** Save each run's timings and prose to `experiments/expander/round3/{arm}/run{n}/`.

**3.3** Produce `experiments/expander/round3/timings.json` with, per arm: every run's stage 2 time, writer time and total; the **median** and **min/max** of each; and the median-to-median delta between arms. Report medians as the headline, not means — three runs, and one slow outlier would drag a mean.

**3.4** Also record, per arm, the **per-section writer time**, not only the aggregate. If explanation (b) is right, the skip arm's individual writer calls should be uniformly slower; if it is noise, the slowness will sit in one or two calls.

## 4. Reading the result

- **Medians within ~15s of each other** → explanation (a), noise. Timing is neutral; the decision rests on the architectural case alone.
- **Skip arm median slower by a margin larger than each arm's own min–max spread** → explanation (b), real. Removing the expander genuinely costs latency by concentrating work in one expensive call.
- **Skip arm median faster** → the round-2 result was itself the outlier; deletion wins on both quality and speed.

Note for interpretation (do not act on it, just report it): under lanes, the expander cost is per-lane and parallel, so a 27s stage-2 cost is not 27s of wall clock in the final architecture — while a slower writer call sits on the critical path of every lane. If (b) holds, that asymmetry matters more than the raw totals suggest.

## 5. Reporting and the stop

Write the report into `RESTRUCTURE_PROGRESS.md` under `## AWAITING DECISION: expander (round 3 — timing)`: the six runs, per-arm medians and spreads, per-section writer times, and a factual statement of which explanation the numbers support. Do not recommend deletion or retention — the user decides with the architectural case in hand. Commit and halt.

## 6. Stop conditions

- The fixed plan does not reproduce, or the harness differs from round 2 in any way that would make the numbers incomparable — report rather than substituting.
- Provider errors or rate limiting affect some runs but not others — report which runs were affected; do not silently retry and fold them into the medians.
- Any temptation to "improve" the writer prompt mid-round — do not; that is a different experiment.

Record under `## BLOCKED`, commit, halt.

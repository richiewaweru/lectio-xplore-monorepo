# 04 — Speed summary

Both runs terminated at the same stage, so there is no end-to-end generation time
to report. What follows is what was actually measured, and nothing else.

## Measured stages

| Stage | Run A (Science) | Run B (Economics) |
|---|---|---|
| Readback (`constructor/readback`) | 15s | 16s |
| Readback review + unit create (`POST /units`) | 31s | 1m 34s |
| **Path planning** (`path:plan`) | **2m 49s** | **3m 00s** |
| Path approval (`path:approve`) | <1s server-side | <1s server-side |
| **Lesson preparation to failure** (attempt 1) | **1m 43s** | **1m 29s** |
| Lesson preparation to failure (attempt 2) | 1m 27s | 1m 28s |
| Total T0 → terminal failure | 12m 38s | 12m 46s |

Wall-clock totals include operator review time between steps and are not a
throughput measure.

## Stages that could not be measured

Everything downstream of the structural plan. These are **not** "too fast to
observe" — they never executed:

```text
T5  structural plan approved      never reached
T6  teaching plan visible         never reached
T7  teaching approval submitted   never reached
T8  approval response / queued    never reached
T9  planning_forms                never reached (this run)
T10 writing_blocks                never reached
T11 assembling                    never reached
T12 awaiting_visuals              never reached
T13 ready                         never reached
T14 viewer rendered               never reached
T15 teacher PDF result            never reached
T16 student PDF result            never reached
```

No timings are invented for these.

## Assessment

**Slowest measured stage: path planning**, at 2m 49s / 3m 00s. Both runs are within
11 seconds of each other despite different subjects and lesson counts (4 vs 6), so
the cost appears dominated by a single long provider call rather than by scaling
with output size.

**Provider latency** accounts for essentially all measured time. Every stage that
took more than a second was waiting on `api.deepseek.com`; all model traffic in the
run went to that host. Backend-local work (`path:approve`, unit persistence,
`/units` hydration) returned in well under a second throughout.

**Queue delay: not applicable.** Nothing was ever queued. The one queue observation
available is incidental but positive: at backend startup the native worker claimed a
leftover queued job within ~2.5 minutes of coming up, so the claim loop itself is
alive.

**Visual delay: not applicable.** No figure was ever requested.

**UI delay: negligible, with one caveat.** The SvelteKit frontend was responsive and
the status text (`Setting up your lessons…`, `Making the lesson…`) tracked the real
request state correctly. The caveat is the *first* vite start took 36–40s to become
ready, which is a cold-start cost, not a per-interaction cost.

**Unexpected idle time: none.** Every measured gap corresponds to a request that was
genuinely in flight. There was no observed period where the system was idle while
appearing busy.

**Science vs Economics difference: negligible.** Path planning differed by 11s
(2m49s vs 3m00s) even though Economics produced 50% more lessons and additionally
raised an assumption for resolution. Preparation-to-failure was also nearly
identical (1m43s/1m27s vs 1m29s/1m28s). On the evidence available, subject and
lesson count are not meaningful drivers of latency in these stages.

## Note on the failure latency

The preparation failures are not fast failures. Each burned roughly 1.5 minutes of
provider time before the response was rejected by a local validator. Because the
structural planner has no repair loop, that time is spent and discarded. If the
schema were enforced at generation time (see `03-error-log.md`, E1), that cost would
either be avoided or be recoverable.

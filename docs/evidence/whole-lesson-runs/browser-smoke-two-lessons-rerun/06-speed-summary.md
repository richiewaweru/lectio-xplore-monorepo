# 06 — Speed summary (rerun)

## Measured

| Stage | Time | Notes |
|---|---|---|
| Unit creation (readback + `POST /units`) | ~1m 32s | readback ~15s of that |
| **Lesson preparation (`:prepare`)** | **1m 29s** | succeeded first attempt; structural planner + repair loop available but not needed |
| Structural approval (`/v3/chunked/approve`) | sub-second | server-side |
| Backend cold start (with migrations) | ~35–45s | includes alembic |
| Frontend cold start (vite) | ~36–40s | first start only |

### Preparation is the number that matters

1m 29s, first attempt, no repair needed. For comparison, on the starting commit
the same call burned:

```text
1m 43s -> 422
1m 27s -> 409
1m 29s -> 409     (Economics, previous run)
1m 28s -> 409     (Economics retry, previous run)
```

That is roughly 6 minutes of provider time across four attempts, all discarded.
The fix converts that into one successful 1m 29s call. The repair attempt added by
this change did not fire, so it cost nothing here — the typed schema alone was
sufficient, which is the intended design (schema primary, repair as the net).

## Not measurable

Path planning cannot be reported as a product timing this run. Five attempts:
three died in the database layer, one was rejected by product validation, one
completed. Their durations measure the environment fault, not the planner.

For scale only, the planner phase alone (planner + 5 merge critics, measured
in-process where it succeeded) ran several minutes. Lesson count varied between 6
and 8 for identical input, and each additional lesson adds a merge-critic call, so
this stage is inherently variable.

Everything downstream of structural approval — teaching plan wait, approval
response, queue delay, form planning, writing, assembly, visual wait, viewer load,
PDF — was **not reached**. No timings are invented for those.

## Assessment

**Slowest stage that was cleanly measured: lesson preparation**, at ~1m 29s,
essentially all provider latency. Backend-local work (approval, persistence,
page hydration) was sub-second throughout.

**Provider:** all model traffic went to `api.deepseek.com`. FAST =
`deepseek-v4-flash`, STANDARD = `deepseek-v4-pro`.

**Queue delay, visual delay, ready-to-view:** not applicable — not reached.

**Unexpected idle time:** yes, and it dominated the session. Not idle *within* a
request, but idle between them: the backend had to be restarted before most stages
because it degrades to returning 500 on every request after a few minutes of
uptime. Roughly half the wall-clock time of this run was spent restarting servers
and re-establishing state rather than generating anything.

**One efficiency note for future runs:** disabling reasoning on the two
constrained DeepSeek nodes should reduce their latency as a side effect, since
thinking tokens are no longer generated. I did not isolate a before/after
measurement for that, so it is stated as an expectation, not a result.

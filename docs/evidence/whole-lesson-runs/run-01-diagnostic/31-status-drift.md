# Status drift and the "Prepare fails" impression

Prepare works (see `30-prepare-forensics.md`). Three separate defects around it plausibly
produce the user-visible impression that it does not.

---

## Drift 1 — `generations.status` never leaves `awaiting_review` (STATUS_DRIFT)

After the teacher approved the structural plan in the browser
(`POST /api/v1/v3/chunked/3f40587d-4846-4fdb-a07f-3eb48b0a2257/approve -> 200`,
`15:32:07.143`, `request_id=eade8a21`), the two sources of truth disagree and stay
disagreeing:

| Source | Value | Correct? |
|---|---|---|
| `generations.status` | `awaiting_review` | **stale** |
| `chunked_state_json.stage` | `stage2_running` | current |
| `chunked_state_json.execution_started` | `false` | — |
| Provider activity | two DeepSeek calls after approval (`15:32:08`, `15:34:08`) | work *is* running |

The generation row still claims it is waiting for a review that the teacher already
gave, while the chunked state and the provider traffic both show stage 2 executing.

**Why this matters.** Any consumer that trusts `generations.status` — a dashboard, a
list view, a support query, a stale-generation sweep — sees a lesson stuck at
"awaiting review" while it is in fact mid-generation. Note the startup sweep
`V3GenerationWriter.fail_stale_running()` (`src/app.py:227`) keys off running state; a
status that never advances is exactly the kind of thing that makes such sweeps
unreliable.

---

## Drift 2 — the approval click produces no visible UI change (RENDER)

Clicking **Review concepts** at `15:31:53.567` fired the approve request and advanced
the backend to `stage2_running`. The Studio page then rendered **exactly the same
content as before** — same structural plan, same three buttons, no progress indicator,
no stage label, no acknowledgement.

Screen text before and after the click is byte-identical.

From the teacher's seat this is indistinguishable from "the button did nothing".
Combined with Drift 1, a user who then checks status sees `awaiting_review` and
reasonably concludes preparation failed. **This is the most likely explanation of the
reported symptom.**

---

## Drift 3 — SSE stream fails, UI falls back to a polling storm (API / efficiency)

```
GET /api/v1/v3/chunked/3f40587d-4846-4fdb-a07f-3eb48b0a2257/events
    [FAILED: net::ERR_ABORTED]
```

The event stream never establishes — and no corresponding request appears in the
backend log at all, so it fails before reaching the application. The UI falls back to
polling, and the fallback is aggressive. Sampling 40 consecutive backend HTTP log
records during stage 2:

| Endpoint | Requests in sample |
|---|---|
| `/v3/chunked/{id}/status` | 19 |
| `/v3/generations/{id}/document` | 19 |
| `/health` (my probe) | 2 |

Two full round trips per cycle, one of them `/document`, which is refetched
continuously even though no document exists yet (`document_json IS NULL`). This is
pure waste against the backend and the database for the entire multi-minute generation,
and it means the UI is doing the most expensive possible thing to learn nothing changed.

---

## Consistency table at the observed transitions

| Moment | `generations.status` | `chunked_state.stage` | `execution_started` | UI shows | Consistent |
|---|---|---|---|---|---|
| After Prepare `200` (15:24:38) | `awaiting_review` | `awaiting_review` | `false` | structural plan for review | **yes** |
| After structural approve `200` (15:32:07) | `awaiting_review` | `stage2_running` | `false` | unchanged structural plan | **NO — drift 1 + 2** |

---

## What is *not* drifting

* `native_whole_lesson = true` is set consistently and the native path is genuinely
  engaged — the structural prompt used is the page-oriented one, and the stored plan
  carries `document_contract_version: 2`.
* `path_prepared = true` matches reality.
* `failed_sections` is empty and no `error`/`error_type`/`error_code` is set anywhere —
  there is no hidden failure being masked.

---

## Drift 4 — a failed lesson cannot be retried from the UI (ORCHESTRATION)

Observed while re-running after the validator fix. `POST …:prepare` is idempotent per
path lesson and **returns the existing generation regardless of its state**:

| Attempt | Generation state before | `:prepare` result | Generation returned |
|---|---|---|---|
| Run B (16:03:20) | `stage2_error` | **200** | `3f40587d…` — the same dead one |
| Run C (16:31:19) | `failed`, `error_type=server_restart` | **200** | `3f40587d…` — still the same one |

Prepare reports success and hands back a generation that has already failed twice. There
is no browser path from a failed lesson back to a working one — the "Prepare Lesson"
button cannot recover it, and the unit page still advertises *"Ready when you are"* with
no indication that a preparation exists, let alone that it died.

The only way to re-drive the pipeline was to re-issue the **structural approval**
(`POST /v3/chunked/{id}/approve`), which does re-run stage 2 from `stage2_error`. That is
not a discoverable recovery path for a teacher.

---

## Addendum to Drift 1 — `generations.status` *can* be written; the error path just doesn't

The startup stale sweep (`V3GenerationWriter.fail_stale_running()`, `src/app.py:227`)
set the row to `status=failed, error_type=server_restart` on the next restart. So the
column is writable and other code paths do maintain it.

That sharpens the diagnosis: this is not a missing mechanism, it is specifically the
stage-2 failure handler in `generation/v3_studio/router.py` neglecting to record the
outcome on the generation row. The only durable trace it leaves is
`chunked_state.stage = stage2_error`.

Note the side effect: the sweep's `server_restart` label then **overwrites the real
cause**. Anyone reading that row afterwards sees "failed because the server restarted",
not "failed because the teaching plan did not validate".

---

## Drift 2 — closing the loop: the UI *can* show the error, it is just never told

Later in the run, after the startup stale sweep set `generations.status = failed`, the
Studio page immediately rendered a red message:

> **Generation failed before a resource snapshot was saved.**

Same generation, same `chunked_state.stage = stage2_error`, same missing teaching plan —
the only thing that changed was `generations.status`.

**This is conclusive.** The Studio failure banner is driven by `generations.status`, not
by `chunked_state.stage`. Because the stage-2 error handler never writes the generation
row, the UI has nothing to react to and keeps polling a success screen. When something
else finally wrote `status=failed` — the *restart sweep*, minutes later and for the wrong
reason — the banner appeared at once.

So P1-1 and P1-3 collapse into a single fix: **write the failure to the generation row
and the existing UI will surface it.** No frontend work is required for the error to
become visible; the message is already implemented and waiting.

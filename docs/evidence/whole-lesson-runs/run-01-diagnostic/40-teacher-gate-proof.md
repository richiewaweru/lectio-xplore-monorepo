# Teacher approval gate — proof (run D)

**Generation:** `ee64d939-6f31-4fc4-9702-395580d25302`
**Lesson:** "Plants as Producers" (path lesson `fc9e4f92-7a3e-495e-b4e7-d83052da222e`,
position 0, `conceptual`, objective *"Recognize that plants are producers that make their
own food"*).

A second lesson from the same approved path was prepared after Corrections 4 and 5,
because the first generation could not be recovered once it had failed (see
`31-status-drift.md`, Drift 4).

## The teaching plan validated

```
teaching_validation = {"ok": true, "issues": []}
```

Event trail — complete and correctly ordered, unlike the failed run:

```
17:00:39.129  teaching_plan_started      status=started
17:06:17.180  teaching_plan_ready        status=ready    (+ full arc text)
17:06:17.222  awaiting_teaching_approval status=pending
```

Teaching planner: 2 attempts, 17:00:39 -> 17:06:17 = **338 s**.

## BEFORE approval — downstream is genuinely blocked

State captured while `stage = awaiting_teaching_approval`:

| Slot | Value | Meaning |
|---|---|---|
| `teaching_plan` | object(4) — `anchor_usage`, `arc`, `misconception_focus_ids`, `sections` | produced |
| `teaching_prompt` | string(29,353) | retained |
| `teaching_raw` | string(8,410) | retained |
| `teaching_validation` | `{ok: true, issues: []}` | passed |
| `teaching_review.status` | `pending` | awaiting teacher |
| **`form_plan`** | **null** | **form planning has NOT begun** |
| **`form_prompt` / `form_raw` / `form_validation`** | **null** | **no form work at all** |
| **`block_execution`** | **object(0)** | **no writer has run** |
| **`document_revision`** | **0** | **no document produced** |
| **`generations.document_json`** | **NULL** | **nothing assembled** |
| `execution.worker_id` | null | worker has not claimed |
| `execution.document_sha256` | null | nothing persisted |
| `execution_started` | false | — |

**The gate holds.** Nothing downstream of the teacher runs before the teacher acts.

Note also that on the success path `teaching_prompt` and `teaching_raw` **are** persisted
(29 KB and 8.4 KB). They were `null` in the failed run — confirming that the raw model
artefacts are dropped exactly when they would be most useful for debugging.

## Teaching plan quality (reviewed in protocol order)

The Studio review screen instructs *"Read the last brief first"* and renders the sections
in reverse order — CHECK, CONTRAST, EXPLAIN, ORIENT — matching the review protocol.

* **Last brief first** (`check-b1 · check-understanding`): five diagnostic questions
  drawn from the approved items — substantive, not a stub.
* **First brief** (`orient-b1 · orient`): "Describe a garden where plants grow larger each
  day. Note that nobody adds food… 'If no one feeds them, where does the plant's food come
  from?'"
* **The final brief is not materially weaker than the first** — the protocol's key check.
* **Arc**: coherent mystery → leaves → mechanism → contrast → check.
* **Anchor usage**: declared per slot (`orient`, `explain`, `check`); `confront` is empty,
  consistent with that slot being removed upstream by the
  `misconception.confront_per_belief` toggle.
* **Misconceptions**: `M1`, `M2` focused; `contrast-b2 · warn` explicitly counters
  "plants eat sunlight".
* **Scope respected**: briefs say "Do not mention glucose or chemical equations" and
  "Do not discuss chloroplasts" — matching `must_not_introduce` exactly.
* **No page-object ids** appear in any brief.

## Approval, through the browser

```
POST /api/v1/v3/generations/ee64d939-6f31-4fc4-9702-395580d25302/lesson-approach/approve
-> 202 Accepted        17:13:38
```

`202` — the async queued response the architecture calls for, not a blocking `200`.

Approval was performed by clicking **Approve teaching plan** in the UI. It was not
scripted and not auto-approved.

*(An earlier click at 17:10:37 produced no request — the element had shifted after a
re-render. That was a mis-click on my part, not a product defect; the backend log shows
no request for it, and the next click worked normally.)*

## AFTER approval — downstream starts

```
teaching_review.status : pending -> approved
generations.status     : awaiting_teaching_approval -> planning_forms
chunked_state.stage    : awaiting_teaching_approval -> planning_forms
```

Execution advanced to form planning immediately on approval and not before it.

**Verdict: the teacher approval gate is CONFIRMED working in both directions** — it
blocks form planning and writers while pending, and releases them on approval.

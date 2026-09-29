# Deferred convergence: plan generation and Learn/Print job tracking

Prepared 2026-09-29 for planning. **Nothing here is implemented yet.** This explains the two deferred items from the closeout (items 3 and 4): what they are, why they matter, and what doing them would take.

---

## 1. The one-paragraph version

The app has **one job system** (`generation_runs` / `generation_work_items`). It is used for writing the lesson document, and it is solid: every step is recorded, retried a bounded number of times, leased so two workers never collide, and verified by hash. But two other parts of the product still run on **older, home-made job tracking** from before that system existed:

- **(A) Plan generation:** preparing a lesson and writing its Teaching Plan (item 3).
- **(B) Learn/Print output jobs:** turning a finished document into a Learn lesson or a Print booklet (item 4).

Both work today. They are just built differently, so there are three ways of saying "running / failed / retry" instead of one. Converging them means moving A and B onto the same job system the document already uses.

---

## 2. What happens today, step by step

```text
Teacher clicks "Prepare lesson"
   │
   ▼
(A) PLAN GENERATION  ← older mechanism
   • generate concept cards + practice/check items (LLM)
   • write the V2 Teaching Plan (LLM planner + LLM reviewer)
   • wait for teacher approval
   │  (teacher approves)
   ▼
SHARED LESSON DOCUMENT  ← the new job system (generation_runs)
   • sourcebook → tasks → compose → write → boundaries → images → QA → READY
   │
   ▼
(B) LEARN / PRINT OUTPUT JOBS  ← older mechanism
   • Learn: turn the READY document into an interactive lesson
   • Print: turn it into a booklet (+ answer key, visuals, PDF)
```

### How (A) plan generation runs today
| Aspect | Today |
|---|---|
| Where the status lives | The `generations` table: a `status` column **plus** a `stage` inside a JSON blob (`chunked_state_json`) **plus** a second status inside another nested JSON (`page_document_v2.execution`). Three places that must be kept in agreement. |
| Who runs it | A background task started inside the web server when the teacher clicks Prepare (`application/unit_lesson/native_pipeline.py`). It is tracked only in the server's memory. |
| If the server restarts mid-way | Before this week the lesson stayed "running" forever. P12A added a heartbeat and a cleanup sweep, so it now becomes "failed – retry" after about a minute. That is a patch, not a real job system. |
| Retries | A separate retry mechanism (`native_retry.py`, about 550 lines) with its own rules for which step to redo. |
| Status names | `pending`, `stage2_running`, `item_generation`, `planning_teaching`, `awaiting_teaching_approval`, `awaiting_review`, `completed`, `failed`, `failed_recoverable`, … The frontend plan page understands these through its own list (`plan-status.ts`). |
| Where the code lives | Historically inside the **Print** folder (`print/generation/whole_lesson/…`, `print/http/v3_studio/router.py`), even though it now serves both Learn and Print. The "v3" name is from an earlier generation of the product. |
| Observability | Events live in a JSON list on the row. There is no per-step history like the document job has. |

### How (B) Learn/Print output jobs run today
| Aspect | Today |
|---|---|
| Where the status lives | A `native_realizations` table (one row per Learn or Print output) plus a status on the output's `generations` row. |
| Who runs it | Two separate polling workers: the Learn worker (`learn/generation/worker.py`) and the Print worker (`print/generation/whole_lesson/worker.py`). Each has its **own copy** of lease/heartbeat logic, stored in JSON (`learn/generation/fencing.py`, `whole_lesson/repository.py` ≈ 2,500 lines). |
| What the job actually does now | Very little. Since Phases 10–11, both are deterministic adapters: read the READY document and reshape it. No LLM calls. Print additionally handles figure images and the PDF export. |
| Status shown to the teacher | Through `/api/v1/realizations/{id}/status` (`progress_routes.py`) and the frontend's `reliability.ts`, a third status vocabulary. |
| Bugs from this duplication | The live check this week found the Learn worker spinning 800+ times while waiting for a document. That was a bug in the bespoke worker loop, which the shared job system already handles correctly. |

---

## 3. What "converging" would mean

Each of A and B becomes a **Run** in the shared job system, broken into **work items**, exactly like the lesson document is today:

| Today | After convergence |
|---|---|
| Plan generation background task | A `preparation` Run with work items such as `items:<concept card>` (one per card, retried independently), `teaching_plan`, `plan_review`. It stops at a durable **awaiting approval** state. |
| Learn realization row + Learn worker | A `learn_realization` Run with a `learn:realize` work item (and `learn:publish` if wanted). |
| Print realization row + Print worker | A `print_realization` Run with `print:realize`, `print:visuals`, `print:pdf` work items. |
| Three status vocabularies | One: `queued / running / awaiting_review / ready / failed_recoverable / failed_terminal / cancelled`, plus a "what to do next" action (retry / review / regenerate). |
| Three lease/heartbeat implementations | One (already built and tested). The P12A heartbeat patch and both bespoke workers are deleted. |
| Status endpoints `/v3/chunked/{id}/status` and `/realizations/{id}/status` | One run-status endpoint (already exists: `/api/v1/generation/runs/{id}`). The frontend reads one shape everywhere. |

### What you'd gain
- **Reliability by construction.** Crashes, retries, duplicate clicks and two workers racing are handled the same, already-proven way everywhere.
- **Retry just the failed piece.** For example, retry one concept card's items instead of re-running the whole preparation.
- **One timeline per lesson.** You could see prepare → plan → approve → document → Learn/Print as one history of runs and events: easier debugging, cost and latency tracking.
- **Much less code.** Roughly 5,000 lines of duplicate job machinery removed (the P12 audit estimate). The historical "v3"/"Print folder" names disappear from the planning path.
- **A simpler frontend.** One status model instead of three lists that must be kept in sync.

### What it costs and what makes it risky
| Concern | Detail |
|---|---|
| **Size** | Plan generation: about 1–2 weeks. Learn/Print jobs: about 1 week. They can be done separately. |
| **Database migration** | New run types, and a mapping for existing lessons. Existing prepared lessons, approved plans and outputs must keep working. Their current status has to be mapped once (backfill), or they're left read-only under the old tables until they are regenerated. |
| **Approval guarantees** | The approved-plan hash is what everything downstream trusts. The migration must copy these identities exactly, never recompute them, or approved lessons would look "changed". |
| **Frontend** | The plan page, Learn page and Print page switch to the shared run-status shape. It's moderate work; the review page already uses the new system. |
| **Behaviour change risk** | Plan generation is the entry point for every new lesson. A mistake there blocks everything, so it needs a staged rollout: new lessons on the new path, old ones untouched. |

---

## 4. Options

| Option | What | Effort | When it makes sense |
|---|---|---|---|
| **A. Leave as is** | Keep today's working mechanisms, now crash-safe (P12A) and cleaned up (P12B/P13). | 0 | If you want to focus on content quality and users first. |
| **B. Learn/Print jobs only** (item 4) | Move Learn/Print output jobs onto the shared system. These jobs are now simple adapters, so this is the **safer, smaller** half. It removes two bespoke workers and one status vocabulary. | ~1 week | A good first step: low risk, visible cleanup, and it proves the migration pattern. |
| **C. Plan generation** (item 3) | Move preparation + Teaching Plan onto the shared system, with per-card retries and a durable approval wait. | ~1–2 weeks | After B. This gives the biggest reliability gain and removes the last "v3" architecture. |
| **D. Both, B then C** | The full convergence: "one lesson-generation architecture" with no history needed to explain it. | ~2–3 weeks | If you want the architecture fully finished before scaling up usage. |

**Recommendation:** D, in the order B → C, as a planned project with a short design note first. That note would cover the Run/work-item layout, the DB migration and backfill plan, and the frontend status mapping. It should come after your signed-in inspection (item 5), so real usage can inform it.

---

## 5. Glossary
- **Run:** one tracked job, e.g. "write the document for lesson X". It has a status, attempts and a history.
- **Work item:** one step inside a Run, e.g. "write section 3". It can be retried on its own.
- **Lease / heartbeat:** a worker's claim that it is currently doing a step. If the worker dies, the claim expires and another worker can pick the step up safely.
- **Realization:** turning the finished lesson document into a specific output (Learn lesson or Print booklet).
- **v3 / native / chunked:** historical names from earlier versions of the product. They describe *when* code was written, not what it does.

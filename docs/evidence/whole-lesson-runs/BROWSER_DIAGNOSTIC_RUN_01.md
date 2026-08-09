# Xplore Browser Diagnostic Run 01

**Date:** 2026-08-07 · **Driver:** real browser UI at `http://localhost:5173`
**Supporting evidence:** `run-01-diagnostic/` · **Machine-readable latency:** `run-01-diagnostic-latency.json`

---

## 1. Executive result

```
Overall result:            PARTIAL — but far deeper than any previous attempt
Furthest stage reached:    awaiting_visuals (document assembled, persisted, reload-verified)
Primary blocker (found):   DATA_CONTRACT — teaching-plan validator required a machine id
                           inside prose; FIXED during this run (Corrections 4 + 5)
Current blocker:           ORCHESTRATION — pipeline stalls at awaiting_visuals; a visual
                           is requested for block explain-b1 and no image-provider call
                           is ever made
Unit ID:                   907b1dab-11fd-49fc-ac23-060d45b446b8
Generation (run A-C):      3f40587d-4846-4fdb-a07f-3eb48b0a2257  (teaching planner FAILED)
Generation (run D):        ee64d939-6f31-4fc4-9702-395580d25302  (reached awaiting_visuals)
Document SHA-256:          c3d7566a4486e590c96a30d09369c5b0e62072aa4339b123c1c059b9b6c64708
                           written, reloaded and hash-verified in Docker Postgres
Total wall clock:          15:13:10Z -> 17:17:31Z = 2 h 4 min (incl. fixes and 4 runs)
```

### What changed during the run

Four browser-driven attempts. The first three used one generation; the fourth used a
fresh one after two validator corrections.

| Run | Code state | Teaching-plan blocking issues | Outcome |
|---|---|---|---|
| A | baseline | **8** | `stage2_error` |
| B | + Correction 4 (anchor vocabulary) | **2** | `stage2_error` |
| C | + Correction 5 (must_establish fallback) | **1** (`INTENT_LEGALITY` — a *different*, legitimate rule) | `stage2_error` |
| D | same code, fresh generation | **0** | **teacher gate -> form planner -> writers -> document -> reload verified**, then stalled at `awaiting_visuals` |

### Confirmed working, end to end, in the browser

* Prepare Lesson, structural planning, structural review gate
* Item generation (fragile — see retries)
* **Teaching planner** (after the fixes)
* **Teacher approval gate — blocks form planning and writers while pending, releases on approval**
* **Form planner**
* **Writers** (8 blocks,genuinely parallel)
* **Assembly into LectioDocumentV2, persistence to Docker Postgres, and hash-verified reload**

### Still not proven

* Viewer render of the reloaded document
* Teacher and student PDF export, and the answer-visibility difference

### The question this run was created to answer

> *"What exactly happens from clicking Prepare Lesson onward, where does the real
> application stop, why does it stop, how long does each stage take, and what state has
> actually been persisted when it stops?"*

**Prepare Lesson does not fail.** It returned `200` in 44.7 s, created a generation,
called the structural planner, persisted a real structural plan, and parked at the
structural review gate — which is a designed teacher checkpoint.

The application actually stops **four stages later**, in the **teaching planner**, on a
validation rule that cannot realistically be satisfied. And it stops *invisibly*: the
generation row still says `awaiting_review` with `error`, `error_type` and `error_code`
all `NULL`, while the UI shows the original plan and its buttons as if nothing had
happened. A teacher waits forever and concludes "preparing the lesson failed".

**So the reported symptom is real, but its stated cause is wrong.** Prepare succeeds
internally; the UI/status/orchestration make a later failure look like a Prepare failure.

---

## 2. Environment

| Item | Value |
|---|---|
| Branch | `pageobject-integration` @ `d0ded68` |
| Branch note | The brief expected `whole-lesson-native-e2e`. That branch is **fully contained** in `pageobject-integration` (13 commits ahead, 0 behind), so no switch was made. |
| Frontend | `http://localhost:5173` — Vite 7.3.6, strict port |
| Backend | `http://127.0.0.1:8000` — uvicorn, **no `--reload`**, unbuffered, logs captured |
| Backend instance | `7f505a6d-6c0e-49cc-8b76-91a4d992fc71` |
| Docker service | `textbookagent-db-1` (compose project `textbookagent`, service `db`) |
| Postgres | 16.9 (alpine), `textbook_agent`, `127.0.0.1:5432` |
| Migrations | `20260806_0032 (head)` == heads |
| Flags | `xplore_v2_enabled=True`, `xplore_page_documents_enabled=True`, `xplore_page_document_scope=all`, `xplore_native_worker_enabled=True` |
| Models | structural / items / teaching all `deepseek-v4-pro` via `openai_compatible` at `api.deepseek.com` |
| Provider keys | DeepSeek, Anthropic, OpenAI, XAI, Google present; Groq absent. **No values recorded anywhere.** |

**Deviations from the brief, all deliberate and recorded:**

* `db-dev` was not used. It has never been started (no `pgdata_dev` volume) and binds the
  same host port as the already-running `db`. Per user decision the run used `db`, which
  is the same local Docker Postgres 16 image on the same port that `backend/.env` targets.
  The requirement that matters — local Docker, not Railway — is proven.
* `XPLORE_PAGE_DOCUMENT_SCOPE` is `all`, not `conceptual_first_exposure`. `all` is a
  superset that still routes this conceptual/first-exposure lesson natively.
* The unit form is now a single free-text field, not separate title/objective/knowledge
  inputs. All specified content was supplied there and the readback parsed it exactly.

---

## 3. Docker database proof

**BACKEND CONNECTED TO DOCKER POSTGRES: YES**

Two-sided identity, both over TCP — full detail in `run-01-diagnostic/db/00-DOCKER_DB_IDENTITY_PROOF.md`.

| Field | Docker side (`psql -h 127.0.0.1`) | App side (app's own SQLAlchemy engine) |
|---|---|---|
| `current_database()` | `textbook_agent` | `textbook_agent` |
| `current_user` | `textbook` | `textbook` |
| `inet_server_port()` | `5432` | `5432` |
| `version()` | PostgreSQL 16.9 | PostgreSQL 16.9 |
| **`system_identifier`** | **`7624095893609250850`** | **`7624095893609250850`** |
| **`pg_postmaster_start_time()`** | **`2026-08-07 06:49:40.520061+00`** | **`2026-08-07 06:49:40.520061+00`** |

`system_identifier` is written at initdb and `pg_postmaster_start_time()` at process
start. Identical values on both sides prove this is the **same PostgreSQL instance**, not
two servers that merely share a name. (`inet_server_addr` differs by design — `127.0.0.1`
from inside the container, `172.20.0.4` from the host through the published port, which
matches `docker inspect`.)

**Railway is not in use.** `DATABASE_URL` resolves to `…@127.0.0.1:5432/textbook_agent`.
`DATABASE_URL_RAILWAY` exists as a separate key that nothing reads.

### DOCKER_DB_PERSISTENCE_PROOF

The unit created through the browser, queried directly inside the container:

```
$ docker exec textbookagent-db-1 psql -h 127.0.0.1 -U textbook -d textbook_agent \
    -c "SELECT id, title, subject, grade_level, status, created_at
        FROM units WHERE id = '907b1dab-11fd-49fc-ac23-060d45b446b8';"

id          | 907b1dab-11fd-49fc-ac23-060d45b446b8
title       | Why Plants Need Light
subject     | Science
grade_level | Grade 4
status      | draft
created_at  | 2026-08-07 15:14:07.685891
```

Browser → backend → Docker Postgres is real and end-to-end.

---

## 4. Browser journey

| # | Action | Request | Result | State transition |
|---|---|---|---|---|
| 1 | Open `/units` | `GET /api/v1/units` | 401 → sign-in | — |
| 2 | Google sign-in (human) | `POST /api/v1/auth/google` | 200 | authenticated |
| 3 | New unit, Science / Grade 4 + free text | `POST /api/v1/units/constructor/readback` | 200 | readback parsed title, topic, objective, prior knowledge exactly as specified |
| 4 | Confirm "That's right" | `POST /api/v1/units` | **201** | unit `907b1dab…` created |
| 5 | (automatic) | `POST …/path:plan` | **201** | path v1, 4 lessons, **no open assumptions** |
| 6 | "Looks good — lock it in" | `POST …/path:approve` | **200** | path draft → **approved** |
| 7 | Select lesson 4, "Why Light is Essential" | `GET …/shape` | 200 | shape `conceptual.first_exposure` |
| 8 | **Prepare Lesson** | `POST …:prepare` | **200** | generation `3f40587d…` created, `awaiting_review` |
| 9 | Studio renders structural plan | `GET /v3/chunked/{id}/plan` | 200 | 4 sections + anchor + question arc rendered correctly |
| 10 | "Review concepts" (structural approval) | `POST /v3/chunked/{id}/approve` | **200** | stage → `stage2_running`; **UI shows no change** |
| 11 | (background) item generation | 3 DeepSeek calls | 2 failed, 1 ok | `item_generation` persisted |
| 12 | (background) teaching planner | 2 DeepSeek calls | **both failed validation** | stage → `stage2_error` |
| 13 | UI after failure | polling `/status` + `/document` | 200s forever | **still shows step 9's screen, no error** |

The lesson chosen was position 3, *"Why Light is Essential"* — `primary_knowledge_type:
conceptual`, objective *"Explain why light is necessary for plants to make food"*, which
is the unit's destination objective verbatim.

---

## 5. Stage latency table

| Stage | Duration | Attempts | Provider / model | Result | Notes |
|---|---|---|---|---|---|
| Unit creation | 6.55 s | 1 | — | PASS | click → row persisted |
| Path planning | 41.84 s | 1 | deepseek (not separable) | PASS | 4 lessons |
| Assumption resolution | — | 0 | — | N/A | none raised |
| Path approval | 9.23 s | 1 | — | PASS | |
| **Prepare lesson (total)** | **44.75 s** | 1 | deepseek-v4-pro | **PASS** | browser wait |
| ├ pre-provider orchestration | 12.88 s | — | — | PASS | mostly browser sequencing |
| ├ structural planner LLM | **31.47 s** | 1 | deepseek-v4-pro | PASS | TTFB 0.47 s |
| └ persistence + respond | 0.40 s | — | — | PASS | 28 KB written |
| *Structural review gate* | *7 m 14.8 s* | — | — | **USER GATE** | **excluded from compute** |
| Structural approval | 13.58 s | 1 | — | PASS | UI showed nothing |
| **Item generation (total)** | **344.9 s** | **3** | deepseek-v4-pro | PASS | 2 failures first |
| ├ attempt 1 | 119.45 s | — | deepseek-v4-pro | **FAIL** | no reason logged |
| ├ attempt 2 | 119.54 s | — | deepseek-v4-pro | **FAIL** | no reason logged |
| └ attempt 3 | 104.33 s | — | deepseek-v4-pro | PASS | |
| **Teaching planner (total)** | **232.4 s** | **2** | deepseek-v4-pro | **FAIL** | validation |
| ├ attempt 1 | 107.97 s | — | deepseek-v4-pro | FAIL | `validation_failed` |
| └ attempt 2 (repair) | 123.10 s | — | deepseek-v4-pro | FAIL | same blocking issues |
| Teacher approval gate | — | 0 | — | **NOT REACHED** | |
| Form planner | — | 0 | — | **NOT REACHED** | correctly gated |
| Writers | — | 0 | — | **NOT REACHED** | no parallel stats exist |
| Assembly / persist / reload | — | 0 | — | **NOT REACHED** | |
| Viewer render | — | 0 | — | **NOT REACHED** | |
| Teacher / student PDF | — | 0 | — | **NOT REACHED** | |

### Where the time actually went

* **Slowest single stage:** item generation, 344.9 s.
* **Slowest single LLM call:** teaching planner repair attempt, 123.10 s.
* **Total provider time:** 605.85 s across 6 calls.
* **Provider time thrown away:** **470.09 s — 77.6 % of all LLM time produced nothing.**
  * item generation retries: 238.99 s
  * teaching planner (both attempts discarded): 231.10 s
* **Backend orchestration + persistence:** 0.40 s measured at Prepare. Negligible.
* **Queue / wait latency:** none — the native worker never had to claim anything.
* **User gate latency:** 434.75 s, excluded from all compute totals.

**The system is not slow because of orchestration or the database.** It is slow because
LLM calls take ~2 minutes each and three-quarters of them are discarded. Postgres
answered in 53 ms; persistence after the model returned took 0.40 s.

---

## 6. Pipeline trace

```
Unit                    PASS   907b1dab-11fd-49fc-ac23-060d45b446b8
 |
Path plan               PASS   4 lessons, no assumptions
 |
Path approval           PASS   v1 approved
 |
Prepare                 PASS   200 in 44.7 s, generation created
 |
Structural plan         PASS   4 sections, anchor, question arc, contract v2
 |
Structural review gate  PASS   rendered; teacher approved in browser
 |
Item generation         PASS   after 2 discarded attempts
 |
Teaching planner        FAIL  <-- STOPS HERE (validation, 2 attempts)
 |
Teacher approval gate   NOT REACHED
 |
Form planner            NOT REACHED
 |
Writers                 NOT REACHED
 |
Assembly                NOT REACHED
 |
Persistence             NOT REACHED
 |
Reload                  NOT REACHED
 |
Render                  NOT REACHED
 |
Teacher / Student PDF   NOT REACHED
```

---

## 7. Failure analysis

### Failure A — teaching plan validation (PRIMARY, classification: **DATA_CONTRACT**)

**Observed symptom.** From the teacher's seat: nothing. The Studio page sits on the
structural plan with Review / Adjust / Regenerate buttons, polling forever. No error, no
spinner, no stage label.

**Exact exception** (available only because of Correction 2):

```
File "…/generation/v3_studio/router.py", line 1319, in _run_chunked_stage2_pipeline
    teaching_summary = await run_and_persist_teaching_plan(
File "…/planning/whole_lesson/service.py", line 163, in run_and_persist_teaching_plan
    result = await run_lesson_approach_planner(
File "…/planning/whole_lesson/teaching_agent.py", line 226, in run_lesson_approach_planner
    raise RuntimeError(
RuntimeError: lesson approach planner failed after 2 attempts: validation_failed issues=[
  {'code': 'BRIEF_NO_ANCHOR_OR_TERM', 'path': 'sections.orient.blocks[0].brief',   'blocking': True},
  {'code': 'BRIEF_NO_ANCHOR_OR_TERM', 'path': 'sections.orient.blocks[1].brief',   'blocking': True},
  {'code': 'BRIEF_NO_ANCHOR_OR_TERM', 'path': 'sections.explain.blocks[0].brief',  'blocking': True},
  {'code': 'BRIEF_NO_ANCHOR_OR_TERM', 'path': 'sections.contrast.blocks[0].brief', 'blocking': True},
  {'code': 'BRIEF_NO_ANCHOR_OR_TERM', 'path': 'sections.contrast.blocks[1].brief', 'blocking': True},
  {'code': 'BRIEF_NO_ANCHOR_OR_TERM', 'path': 'sections.check.blocks[0].brief',    'blocking': True},
  {'code': 'EVIDENCE_REF', 'message': "unknown item evidence_ref 'approved_item_ids'",
   'path': 'sections.check.blocks[0].evidence_refs', 'blocking': True},
  {'code': 'MUST_ESTABLISH_UNCOVERED',
   'message': "must_establish entries not referenced: ['must-1','must-2','must-3','must-4']",
   'path': 'scope.must_establish', 'blocking': False}]
```

**Actual root cause.** The rule at `planning/whole_lesson/validation.py:190`:

```python
if packet.anchor.id not in block.brief and not any(
    term and term in brief_l for term in terminology
):
    ... BRIEF_NO_ANCHOR_OR_TERM
```

It accepts a brief only if the prose contains **the literal anchor ID string**, or a term
from `scope.terminology`. In this lesson:

```
lesson_packet.anchor.id  = "anchor-1"
lesson_packet.scope.terminology = []          <- empty
```

And the terminology path is not merely empty here — it is empty **everywhere**:

```
$ SELECT unit_id, jsonb_array_length(COALESCE(terminology,'[]')) FROM unit_scope_contracts;
 9b1521f9-… | 0
 e087e8e9-… | 0
 f2ac52fe-… | 0
 907b1dab-… | 0        <- all four units in the database
```

So the only surviving way to pass is for the model to write the synthetic token
`"anchor-1"` into human-readable teaching prose. **The prompt never asks for that, and
actively pushes the other way** (`resources/lesson-approach-planner-v1.txt:176`):

```
  - Name concrete things. The anchor by name, the actual terms, the real numbers.
  - Use terminology from scope.terminology.
```

"The anchor **by name**" — i.e. *"the sunflower pair"*, not `anchor-1`. The prompt places
IDs in `evidence_refs` (`"anchor.anchor-plant-window"`), a *different field*, and the same
validator file has an `OBJECT_LEAK` rule that **forbids** ids leaking into briefs. The
producer and the consumer disagree about what a brief is.

Note also the prompt's illustrative anchor id is `anchor-plant-window` (descriptive) while
the packet builder emits `anchor-1` (positional) — even the prompt's example does not
match the data the packet supplies.

| Boundary | Producer | Produced | Consumer | Expected | Verdict |
|---|---|---|---|---|---|
| Teaching prompt → teaching validator | `lesson-approach-planner-v1` | briefs naming the anchor in prose; ids in `evidence_refs` | `validation.py:190` | literal `anchor.id` inside `brief`, or a `scope.terminology` term | **REJECTED — contradictory contract** |
| Scope contract → validator | unit scope generator | `terminology: []` (always) | validator fallback path | non-empty term list | **REJECTED — fallback dead system-wide** |
| Packet builder → prompt example | packet builder | `anchor-1` | prompt shows `anchor-plant-window` | consistent id convention | **mismatched** |

**Input:** lesson packet with `anchor.id="anchor-1"`, `terminology=[]`, 4 must_establish
entries, 1 approved item.
**Output:** a teaching plan with 6 block briefs, discarded twice.
**Last persisted checkpoint:** `item_generation` + `page_document_v2` scaffold
(`schema_version 2`, `lesson_packet` 9 keys, `lesson_legality` 8 keys).
**Why execution stopped:** `RuntimeError` after the retry budget (2) was exhausted;
`_run_chunked_stage2_pipeline` caught it and set `stage2_error`.
**What would have happened next:** `awaiting_teaching_approval` → teacher gate → form
planner → writers → assembly → LectioDocumentV2 → PDFs.

**Secondary issue in the same failure.** `EVIDENCE_REF: unknown item evidence_ref
'approved_item_ids'` — the model emitted the *field name* `approved_item_ids` as if it
were an item ID. The prompt introduces `approved_item_ids` as an input label
(line 31) and separately tells the model to use `source_question_ids` drawn from it
(line 225). The model conflated the two. That is a prompt-clarity defect, and it is
blocking on its own.

**`MUST_ESTABLISH_UNCOVERED` is non-blocking** and did not contribute to the stop.

---

### Failure B — the failure is invisible (classification: **STATUS_DRIFT**)

At the moment of a hard, terminal pipeline failure:

| Source of truth | Value |
|---|---|
| `chunked_state_json.stage` | `stage2_error` |
| `generations.status` | **`awaiting_review`** |
| `generations.error` | **NULL** |
| `generations.error_type` | **NULL** |
| `generations.error_code` | **NULL** |
| `generations.completed_at` | **NULL** |
| `page_document_v2.events` | only `teaching_plan_started` — **no failure event** |
| Frontend | structural plan + Review/Adjust/Regenerate, polling indefinitely |

The traceback exists **only in the process log**. Nothing durable records that this
generation died. Every API-visible surface says "waiting for review".

This is precisely the "backend failed but UI keeps polling / terminal failure has no
useful error" case, and it is why the symptom is reported as "Prepare fails": the user
cannot see where it actually stopped.

---

### Failure C — item generation discarded two full attempts (classification: **LLM_PROVIDER / observability**)

Attempts 1 and 2 each ran ~119.5 s, returned **HTTP 200**, and were then recorded
`llm_call_failed` — with **no reason logged anywhere**. 238.99 s burned with no diagnostic
trail. Attempt 3 (104.33 s) succeeded. Because the reason is not logged and
`teaching_raw`/`teaching_prompt` are left `null` on failure, the model output that caused
it cannot be inspected after the fact.

---

## 8. Database state at failure

```
generations
  id                 3f40587d-4846-4fdb-a07f-3eb48b0a2257
  status             awaiting_review          <- stale
  error              NULL
  error_type         NULL
  error_code         NULL
  section_count      4
  completed_at       NULL
  document_json      NULL

chunked_state_json
  stage              stage2_error             <- the truth
  native_whole_lesson true
  path_prepared      true
  execution_started  false
  failed_sections    []
  structural_plan    {10 keys, document_contract_version: 2}
  section_briefs     {orient, explain, contrast, check}
  item_generation    present
  page_document_v2   present

page_document_v2
  schema_version     2
  lesson_packet      object(9)     <- built
  lesson_legality    object(8)     <- built
  teaching_review    {status: "pending", revision: 1}
  teaching_plan      null          <- never produced
  teaching_prompt    null
  teaching_raw       null          <- model output not retained on failure
  teaching_validation null
  form_plan          null          <- correctly gated
  form_prompt        null
  block_execution    object(0)     <- no writer ran
  document_revision  0
  execution          {attempt: 0, worker_id: null, claimed_at: null,
                      document_sha256: null, reload_verified: false}
  events             [teaching_plan_started]  <- no terminal event
```

---

## 9. Status consistency

| Moment | `generations.status` | `chunked_state.stage` | `execution_started` | UI | Consistent |
|---|---|---|---|---|---|
| After Prepare 200 | `awaiting_review` | `awaiting_review` | false | structural plan for review | **yes** |
| After structural approve 200 | `awaiting_review` | `stage2_running` | false | unchanged | **NO** |
| After teaching planner failure | `awaiting_review` | `stage2_error` | false | unchanged, still polling | **NO** |

**STATUS DRIFT** is present from the moment of structural approval and becomes severe at
failure. `generations.status` never moves after Prepare, regardless of what happens.

Also observed: the SSE stream `GET /v3/chunked/{id}/events` fails with
`net::ERR_ABORTED` and never reaches the backend, so the UI falls back to polling
`/status` **and** `/document` roughly every 4 s — 19 of each in a 40-record sample —
refetching a document that does not exist for the whole multi-minute run.

---

## 10. Corrections made during the diagnostic

Full detail with before/after in `run-01-diagnostic/20-corrections.md`. All three were
made only after the failed state was captured. **No application logic was changed, and
`.env` was not committed.**

| # | Problem | Change | Layer | Verified by |
|---|---|---|---|---|
| 1 | `docker compose` aborted on every command — `apps/textbook-agent/.env` used `//` comments | `//` → `#` on 4 lines (comment syntax only, backup kept) | ENVIRONMENT | `docker compose ps` / `config --services` work |
| 2 | **All application logs discarded after startup** — Alembic `fileConfig()` disabled every existing logger and reset root to WARN | `env.py`: skip `fileConfig` for in-process runs, `disable_existing_loggers=False`; `runner.py`: `config.attributes["configure_logging"] = False` | Backend startup (P0 observability) | isolated repro; `alembic` CLI unchanged; 12 tests pass |
| 3 | One launch started **two** app instances (two native workers; `WinError 10048`); captured log belonged to the dead one | launch via a `__main__`-guarded runner instead of `-m uvicorn`. **No source changed.** | ENVIRONMENT | 0 bind errors, 1 worker, log `instance_id` == `/health` `instance_id` |

Correction 2 is the reason this run produced a traceback at all. The previous run
recorded "application logs are unreadable" as an unsolved blocker and had to reproduce
routes in-process to get any error detail.

**Not changed, deliberately:** `backend/.env` has ~78 duplicated keys (`JSON_LOGS` ×3,
`LOG_LEVEL` ×3, some with literal quotes). Last-wins resolves to a working configuration,
so it was left alone and recorded.

---

## 11. Final architecture assessment

Verdicts reflect the state **after** Corrections 4 and 5, i.e. run D.

| Capability | Verdict | Evidence |
|---|---|---|
| Does the front half work? | **CONFIRMED** | unit → readback → path plan → approve, all 200/201 |
| Does prepare work? | **CONFIRMED** | 200 in 44.7 s; generation + structural plan persisted |
| Does structural approval work? | **CONFIRMED** | `/v3/chunked/{id}/approve -> 200`, stage advanced |
| Does item generation work? | **CONFIRMED (fragile)** | succeeded, but 1–2 attempts discarded every time |
| Does teaching planning work? | **CONFIRMED after fix** | run D: `teaching_validation {ok: true, issues: []}`; BROKEN before Corrections 4+5 |
| Does teacher gate work? | **CONFIRMED** | form_plan/block_execution/document all empty while pending; released on approval |
| Does post-approval execution start? | **CONFIRMED** | `202 Accepted`, stage → `planning_forms` immediately |
| Does form planning work? | **CONFIRMED** | form_plan produced in 63.21 s |
| Do writers work? | **CONFIRMED** | 8 blocks, 10 provider calls, genuinely parallel, 162.70 s wall clock |
| Does assembly work? | **CONFIRMED** | LectioDocumentV2, `document_version: 2`, 4 sections, answer_key |
| Does persistence work? | **CONFIRMED** | `document_json` written to Docker Postgres, 4,278 bytes, revision 1 |
| Does reload work? | **CONFIRMED** | `reload_verified: true`; `document_sha256 == reloaded_sha256 == candidate_sha256` |
| Does render work? | **NOT PROVEN** | documented route `/textbook/[id]` 404s; real route `/studio/generations/[id]` hangs on "Loading session…" with `AbortError` |
| Does PDF work? | **NOT REACHED** | generation never leaves `awaiting_visuals` |
| Answer visibility differs? | **NOT REACHED** | `answer_key` exists in the persisted document; PDFs never produced |
| Native worker | **CONFIRMED starting, UNCERTAIN claiming** | starts cleanly; run D executed inline (`worker_id` null, `attempt` 1) |
| Visual generation | **BROKEN** | `visual_pending` for `explain-b1`; **zero** image-provider calls ever made |
| Is the native path genuinely engaged? | **CONFIRMED** | `native_whole_lesson: true` in packet, chunked state and document metadata; `document_contract_version: 2` |
| Fixtures / legacy conversion | **CONFIRMED ABSENT** | real LLM calls throughout; content traceable to approved briefs |

**Architectural verdict.** The orchestration is sound and, once the validator contract was
corrected, the whole spine works: gates hold in the right order, nothing downstream ran
early, writers parallelise, and the document is assembled, persisted and reload-verified
against Docker Postgres. Two things remain broken and they are at the edges, not the
core: **visual generation never fires**, and the **failure/status reporting** is silent.

## 12. Recommended fixes

### P0 — prevents any lesson completing

**P0-1. Visual generation never fires.** The pipeline requests a visual for one block
(`visual_pending`, `explain-b1`) and then waits forever: **no image-provider call is
ever made**, despite `PIPELINE_IMAGE_PROVIDER=xai` being configured. This is now the
furthest-reach blocker. Also worth checking: the structural plan marked every section
`visual_required: false`, yet the form planner selected a visual anyway.

**P0-2. Keep the validator fixes** (Corrections 4 and 5 in `20-corrections.md`). Without
them the teaching planner rejects essentially every lesson, because it demanded the
literal anchor id inside prose and its only fallback — `scope.terminology` — is empty for
every unit in the database.

**P0-3. Populate `scope.terminology` in the unit scope contract.** Correction 5's
`must_establish` fallback is a stop-gap. The generator should emit real terminology so
the fallback rarely fires.

**P0-4. Disambiguate `approved_item_ids` vs `source_question_ids` in the teaching prompt.**
The model emitted the field name as an item id (run A). Any prompt edit needs a new
prompt version recorded in evidence, since the checksums are frozen.

### P1 — hides failure / prevents recovery

**P1-1. Write terminal failures to the generation row.** On `stage2_error`, set
`status`, `error`, `error_type`, `error_code`, `completed_at` and append a failure event.
**This alone makes the failure visible** — see P1-2.

**P1-2. No frontend work is needed for the error banner.** Studio already implements
*"Generation failed before a resource snapshot was saved"* and rendered it the moment
`generations.status` became `failed`. The UI is not missing an error state; it is never
told. P1-1 fixes P1-3 for free.

**P1-3. Do not let the restart sweep overwrite a real cause.** `fail_stale_running()`
stamped `error_type=server_restart` over a teaching-plan validation failure.

**P1-4. Give a failed lesson a retry path.** `:prepare` returns the same dead generation
forever (200 OK), and the unit page still says "Ready when you are". The only way to
re-drive the pipeline was re-issuing the structural approval — not discoverable.

**P1-5. Retain `teaching_raw` / `teaching_prompt` on failure.** They are persisted on
success (29 KB / 8.4 KB) and `null` exactly when needed for debugging.

**P1-6. Fix the viewer route.** `/textbook/[id]` (still in `CLAUDE.md`) 404s; the real
route `/studio/generations/[id]` hangs on "Loading session…" with repeated
`[chunked stream error] AbortError`.

### P2 — latency and reliability

**P2-1. Log why an `llm_call_failed` failed.** Item generation discarded 1–2 attempts in
every run with no recorded reason.
**P2-2. Attack the discard rate.** In runs A–C, **470 s of 606 s (77.6 %) of provider time
produced nothing**. Two item attempts landing at 119.45 s and 119.54 s is suspicious
against a 120 s ceiling or a token-limit truncation.
**P2-3. Fix `llm_call` telemetry.** Every call logged `Skipping llm_call persistence
without user_id`, so the system cannot report its own tokens, cost or latency; every
timing in this report had to be reconstructed from `httpcore` debug lines.
**P2-4. Ship a `__main__`-guarded entry point** (Correction 3). `-m uvicorn` on Windows
starts **two** app instances and **two native workers**; one dies on `WinError 10048`.
Two workers claiming one queue is a correctness hazard.
**P2-5. Blocker 1 from the previous run did not recur** — 121 `/health` samples over an
hour on local Docker Postgres, zero unexplained failures. Do not treat it as an open
application bug until reproduced off Railway.

### P3 — observability and UI

**P3-1. Fix the SSE `/events` stream** (`ERR_ABORTED`, never reaches the backend).
**P3-2. Stop polling `/document` before a document exists**, and back off from ~4 s.
Two full round trips every 4 s for the whole multi-minute run.
**P3-3. Acknowledge the structural-approval click** — its total silence is the single most
misleading thing in the flow.
**P3-4. De-duplicate `backend/.env`** (~78 repeated keys; `JSON_LOGS` ×3, `LOG_LEVEL` ×3).
**P3-5. Note the 20 s cold Playwright launch** in `/health/ready`; the first PDF export
pays it again.
**P3-6. Update `CLAUDE.md`** — the documented viewer route `/textbook/[id]` no longer exists.

## Constraints honoured

```
Real browser used:                        yes
Fresh unit:                               yes (907b1dab…, created in this run)
Real LLM calls:                           yes (6 DeepSeek calls, no fixtures)
Docker Postgres:                          yes (proven by system_identifier)
Fixtures used:                            no
Fabricated output:                        no
Teacher gate auto-approved:               no (never reached)
Legacy conversion to force a pass:        no
Database rows hand-edited:                no
Manual status changes:                    no
.env committed:                           no
Secrets exposed:                          no
Prompt files edited:                      no
Backend run without --reload:             yes
Latency measured, not estimated:          yes (from process logs and DB timestamps)
```

Unmeasurable values are `null` in `run-01-diagnostic-latency.json`; none were invented.

# Corrections made during the diagnostic

Each correction was made only after the failed state was captured, and each was the
minimum needed to let the run continue.

---

## Correction 1 — compose `.env` could not be parsed (ENVIRONMENT)

**Symptom.** Every `docker compose` command in `apps/textbook-agent` aborted before
doing anything:

```
failed to read C:\Projects\lectio\apps\textbook-agent\.env: line 87:
unexpected character "/" in variable name "//PIPELINE_IMAGE_PROVIDER=gemini"
```

**Root cause.** Four lines in `apps/textbook-agent/.env` were commented out with `//`
instead of `#`. Docker Compose's env parser rejects the file outright. This is the
*compose* env file — separate from, and staler than, `backend/.env`, which the backend
itself reads via python-dotenv (which tolerates the malformed lines, which is why the
backend never surfaced this).

**Change.** `apps/textbook-agent/.env` lines 87–90, `//` → `# `. Comment syntax only;
no value changed. Backup at `.env.bak-diagnostic-run01`. **Not committed** — `.env` is
gitignored.

**Before**

```
//PIPELINE_IMAGE_PROVIDER=gemini
//PIPELINE_IMAGE_MODEL_NAME=gemini
//PIPELINE_IMAGE_BASE_URL=
//PIPELINE_IMAGE_API_KEY_ENV = GOOGLE_CLOUD_NANO_API_KEY
```

**After**

```
# PIPELINE_IMAGE_PROVIDER=gemini
# PIPELINE_IMAGE_MODEL_NAME=gemini
# PIPELINE_IMAGE_BASE_URL=
# PIPELINE_IMAGE_API_KEY_ENV = GOOGLE_CLOUD_NANO_API_KEY
```

**Result.** `docker compose ps` and `docker compose config --services` work.

---

## Correction 2 — all application logs silently discarded after startup (P0, observability)

This is the previous run's **blocker 2** ("application logs are unreadable when
redirected"), which was attributed to stdout block-buffering and never root-caused.
It is not buffering.

**Symptom.** `logs/backend.log` stopped dead after the two Alembic lines. No
`Runtime ready`, no `Application startup complete`, no native-worker line, no request
logs — while the server happily served `/health` 200. Nothing after startup migrations
ever reached any stream, at any level.

**Root cause.** `RUN_MIGRATIONS_ON_STARTUP=true` makes the FastAPI lifespan
(`src/app.py:224`) run Alembic in-process, *after* `configure_logging()` at
`src/app.py:213`. Alembic's `env.py:17` called:

```python
fileConfig(config.config_file_name)
```

`logging.config.fileConfig` defaults to `disable_existing_loggers=True`. It therefore
**disabled every logger already created** — including `uvicorn.error` (the module-level
logger at `src/app.py:57`) and every application module logger imported by then — and
reset the root logger to `alembic.ini`'s `[logger_root] level = WARN` with Alembic's own
stderr handler.

**Proof.** `logs/repro-logging-silenced.txt` — identical process, logging three records
before `fileConfig` and four after:

```
--- BEFORE fileConfig ---
{"level": "INFO",    "logger": "uvicorn.error",                  "message": "A: ... before migrations"}
{"level": "INFO",    "logger": "planning.whole_lesson.service",  "message": "B: ... before migrations"}
{"level": "WARNING", "logger": "uvicorn.error",                  "message": "C: ... before migrations"}
--- AFTER fileConfig ---
--- state after fileConfig ---
root level: WARNING
root handlers: [<StreamHandler <stderr> (NOTSET)>]
uvicorn.error disabled: True
planning module disabled: True
```

Records D–G vanish — **including WARNING and ERROR**. This is why the previous run
could not obtain a traceback and had to reproduce a route in-process to get one.

**Change.** The standard Alembic pattern for programmatic invocation: let the
standalone `alembic` CLI configure logging as before, and opt out when migrations run
inside the app.

`src/core/database/migrations/env.py`

```python
# Only take over logging for the standalone `alembic` CLI. When migrations run
# in-process at app startup, fileConfig() would disable every logger created so far
# and reset root to WARN, silently discarding all application logs — including
# errors and tracebacks — for the life of the process. runner.py opts out.
if config.config_file_name is not None and config.attributes.get("configure_logging", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)
```

`src/core/database/migrations/runner.py`

```python
# In-process migrations must not reconfigure the running app's logging.
config.attributes["configure_logging"] = False
```

**Result.** Logs work end to end:

```
{"level": "INFO", "logger": "resource_specs.loader", "message": "Resource spec registry ready: [...]"}
INFO:     Runtime ready
{"level": "INFO", "logger": "planning.whole_lesson.worker", "message": "Native execution worker started worker_id=native-8e7a515660c3"}
INFO:     Application startup complete.
{"level": "INFO", "logger": "http", "message": "GET /health -> 200", "request_id": "9a18054a", "status_code": 200}
```

**Tests.** `alembic current` via the CLI still prints its own INFO lines (no
regression to the standalone path). `pytest -k "migration or alembic or logging"` →
12 passed.

**Severity beyond this run.** Any deployment with `RUN_MIGRATIONS_ON_STARTUP=true` —
which is the default, and what `docker-compose.yml` sets for the `backend` service —
has had **no application logging at all** after startup, errors included.

---

## Observations recorded but deliberately NOT changed

* **`backend/.env` has ~78 duplicated keys.** `JSON_LOGS` appears three times
  (`false`, `false`, `"true"`), `LOG_LEVEL` three times (`DEBUG`, `INFO`, `"DEBUG"`),
  and provider/timeout keys are widely repeated. Last-wins, so effective values are
  `json_logs=True`, `log_level=DEBUG`. It resolves to something workable, so it was
  left alone — but it makes the configuration very hard to reason about and is a
  latent source of confusion. Some values also carry literal quotes.
* **`XPLORE_PAGE_DOCUMENT_SCOPE=all`** rather than the brief's
  `conceptual_first_exposure`. `all` is a superset that still routes a conceptual
  `first_exposure` lesson down the native path (`src/planning/page_blocks.py:33`), so
  it was left as configured and the deviation recorded.
* **`XPLORE_V2_ENABLED` is absent from `.env`** but defaults to `True`
  (`src/core/config.py:145`), so the required flag state holds.

---

## Correction 3 — one launch started TWO application instances (ENVIRONMENT)

**Symptom.** After the logging fix, `logs/backend.log` still went silent — but this
time from a different cause. The log recorded a complete, healthy startup, yet
`/health` reported a **different** `started_at` than the log showed, and the PID
holding port 8000 was not the PID in the log. The captured log belonged to a process
that was no longer serving.

**Evidence** (`logs/backend-doublestart-evidence.log`), one single launch:

```
INFO:     Started server process [41788]
...
INFO:     Runtime ready
{"logger": "planning.whole_lesson.worker", "message": "Native execution worker started worker_id=native-dccf7f7845a1"}
INFO:     Application startup complete.
ERROR:    [Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000):
          only one usage of each socket address ... is normally permitted
INFO:     Waiting for application shutdown.
{"logger": "planning.whole_lesson.worker", "message": "Native execution worker stopped worker_id=native-dccf7f7845a1"}
```

while `netstat` showed port 8000 held by a *different* PID (`50296`).

**Root cause.** `uv run python -m uvicorn app:app` on Windows. A dependency creates a
`multiprocessing` spawn child (observed in the process table as
`python.exe -c "from multiprocessing.spawn ..."`). Windows `spawn` re-imports
`__main__` in the child — and `__main__` here is *uvicorn's CLI module*, so the child
boots an entire second application: second set of startup migrations, second resource
registry load, and a second `native execution worker`. The two instances then race for
the port; the loser dies with `WinError 10048` after having already started and stopped
a worker. There is no `multiprocessing` usage anywhere in `backend/src` — it comes from
a dependency.

**Why it mattered here.** The instance whose stdout was redirected to the log file was
not reliably the instance that won the port, so log forensics could be silently
attributed to a dead process. This alone would invalidate a diagnostic run.

**Change.** No application source modified. The server is launched through a
`__main__`-guarded runner instead of `-m uvicorn`, so the spawn child re-imports a
module that does nothing:

```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False, log_config=None)
```

**Result — verified single instance:**

```
bind errors (10048):  0
worker starts:        1
log  instance_id:     7f505a6d-6c0e-49cc-8b76-91a4d992fc71
/health instance_id:  7f505a6d-6c0e-49cc-8b76-91a4d992fc71   <- identical
```

The captured log now provably belongs to the process serving the requests.

**Recommendation.** Ship a guarded entry point (`backend/run_server.py` or a
`[project.scripts]` console entry) rather than documenting `-m uvicorn` for Windows
native development. Two concurrent native workers claiming the same job queue is a
real correctness hazard, not only a logging one.

---

## Correction 4 — teaching-plan validator required a machine id inside prose (P0, DATA_CONTRACT)

**Made after** the failure was fully captured (`30-prepare-forensics.md`,
`BROWSER_DIAGNOSTIC_RUN_01.md` §7) and **after the user chose this repair** over
populating `scope.terminology` upstream.

**Symptom.** The lesson approach planner failed both attempts with
`BRIEF_NO_ANCHOR_OR_TERM` on all six block briefs, ending stage 2 in `stage2_error`.

**Root cause.** `planning/whole_lesson/validation.py` accepted a brief only if the prose
contained the literal `packet.anchor.id` (here `"anchor-1"`) or a `scope.terminology`
term. `terminology` is `[]` for **all four units in the database**, so the only surviving
path was for the model to write a synthetic id into teaching prose — which the prompt
never asks for and argues against ("Name concrete things. The anchor **by name**"), and
which the sibling `OBJECT_LEAK` rule in the same file forbids for object ids.

**Change.** Added a third acceptance path: the brief may ground itself in the anchor's own
vocabulary. The id and terminology paths are unchanged, so nothing that passed before
fails now.

```python
_ANCHOR_STOPWORDS = frozenset(""" a an and are as at be been but by for from has ... """.split())

def anchor_terms(description: str) -> set[str]:
    """Significant words from the anchor description, for grounding checks."""
    words = re.findall(r"[A-Za-z][A-Za-z'-]{2,}", description.lower())
    return {w for w in words if w not in _ANCHOR_STOPWORDS}
```

```python
  anchor_vocabulary = anchor_terms(packet.anchor.description or "")
  ...
- if packet.anchor.id not in block.brief and not any(
-     term and term in brief_l for term in terminology
- ):
+ if (
+     packet.anchor.id not in block.brief
+     and not any(word in brief_l for word in anchor_vocabulary)
+     and not any(term and term in brief_l for term in terminology)
+ ):
      -> BRIEF_NO_ANCHOR_OR_TERM
```

**The rule keeps its teeth.** Against this lesson's anchor
(*"A sunflower seedling on a sunny windowsill grows tall and green, while another kept in
a dark closet turns pale."*):

```
anchor terms: another, closet, dark, green, grows, kept, pale, seedling,
              sunflower, sunny, tall, turns, windowsill

PASS - "Open with the two sunflower plants side by side so learners hold a concrete case…"
PASS - "Explain that light supplies the energy the leaf uses…the windowsill plant as…"
FAIL - "This block supports the objective."          <- generic brief still rejected
```

**Tests.** `tests/planning` — **298 passed**. Prompt files untouched, so the frozen
checksums still verify.

**Not fixed here.** The same failure also carried a blocking
`EVIDENCE_REF: unknown item evidence_ref 'approved_item_ids'` — the model emitted a field
name as an item id. That is a prompt-clarity issue and the prompts are checksum-frozen, so
it was left for the team (recommendation P0-2).

---

## Correction 5 — approved-vocabulary fallback when `scope.terminology` is empty (P0, DATA_CONTRACT)

**Made after** Correction 4 was verified to reduce the blocking issues from 8 to 2, and
**after the user chose this repair**.

**Symptom.** With the anchor fix in place, two `explain` briefs still failed
`BRIEF_NO_ANCHOR_OR_TERM`. They were legitimate briefs — they discuss the mechanism
(light → energy → food) without naming the sunflower anchor.

**Root cause.** The rule's two acceptance paths are *anchor* **or** *approved
terminology*. The prompt explicitly tells the planner to introduce the anchor **once** and
return to it — not to name it in every block — so blocks that do not use the anchor are
supposed to be carried by `scope.terminology`. That list is empty for every unit in the
database, so those blocks had nothing legal to match. Correction 4 fixed the anchor path;
this is the other half of the same defect.

**Change.** `planning/whole_lesson/validation.py` — when `scope.terminology` is empty,
derive the accepted vocabulary from the lesson's own `scope.must_establish`, which is
already approved, in-scope content:

```python
if not terminology:
    # scope.terminology is the intended home for approved vocabulary, but the unit
    # scope generator does not populate it today. Without a fallback, any block that
    # legitimately does not name the anchor — the prompt asks for the anchor to be
    # introduced once and returned to, not repeated everywhere — has nothing it can
    # match. must_establish is already approved, in-scope vocabulary for this lesson.
    terminology = set().union(
        *(anchor_terms(entry.statement) for entry in packet.scope.must_establish)
    ) if packet.scope.must_establish else set()
```

**The rule still discriminates.** Derived terms for this lesson: `cannot, drives, energy,
food, light, make, photosynthesis, plants, provides, stops`.

```
PASS [explain]  "State that light energy is what the leaf uses to build food, and that
                 without it the process cannot run."
FAIL [generic]  "This block supports the objective."
FAIL [vague]    "Cover the main idea in a way that suits the class."
```

**Tests.** `tests/planning` — **298 passed**.

**This is a stop-gap, not the final design.** The right long-term fix is for the unit
scope-contract generator to populate `scope.terminology`; the fallback should then rarely
fire. Recorded as recommendation P0-3.

---

## Effect of Corrections 4 and 5 on the teaching planner

| Run | Code state | Blocking issues | Detail |
|---|---|---|---|
| A | baseline | **8** | `BRIEF_NO_ANCHOR_OR_TERM` ×6, `EVIDENCE_REF` ×1, `MUST_ESTABLISH_UNCOVERED` (non-blocking) |
| B | + Correction 4 | **2** | `BRIEF_NO_ANCHOR_OR_TERM` ×2 (`explain` only); `EVIDENCE_REF` cleared |
| C | + Correction 5 | **1** | `INTENT_LEGALITY` ×1 — a *different* rule |

The entire anchor/terminology class of failure is gone. The issue remaining in run C is
`intent 'diagnose-misconception' is atypical for this slot and requires departure_reason`
at `sections.contrast.blocks[1]` — the validator correctly demanding a justification the
model did not supply. **That is the gate working as designed, not a contract defect, and
it was deliberately not patched.**

# 05 — Final report

**Two-run result: `FAIL` — neither lesson reached a native ready viewer.**

Both runs were blocked at the same gate, four preparation attempts in total, zero
successes. No `generation_id` was issued in either run, so the native execution
path downstream of teaching approval was never exercised.

## Result labels

| Run | Subject | Label |
|---|---|---|
| A | Science · Grade 4 | `FAIL_GENERATION` |
| B | Economics · Grade 8 | `FAIL_GENERATION` |

`FAIL_GENERATION` rather than `FAIL_ENVIRONMENT`: the database was reachable, the
frontend and backend ran at the expected commit, authentication worked, the prompt
verification passed, and every provider call returned HTTP 200. The failures are
contract defects in application code.

The separate environment defect (E3, the phantom alembic revision) is real and
blocking for startup, but it was diagnosed and worked around without editing source
or data, and it is not what stopped the lessons.

## Where it stopped

```text
create unit                    OK   both runs
plan path                      OK   both runs
resolve assumptions            OK   Run B (Run A raised none)
approve path                   OK   both runs
select lesson                  OK   both runs
prepare lesson (structural)    FAIL both runs, both attempts   <-- stops here
approve structural plan             never reached
teaching plan                       never reached
awaiting_teaching_approval          never reached
approve teaching plan               never reached
queued                              never reached
worker claim                        never reached
planning_forms                      never reached (this run; see E2)
writing_blocks                      never reached
assembling                          never reached
awaiting_visuals / ready            never reached
persisted LectioDocumentV2          never reached
native viewer                       never reached
```

## The two blockers

**E1 (stops this run).** `PathStructuralPlan` declares `cards: list[dict]` and
`sections: list[dict]` (`planning/models.py:383-386`) and is used directly as the
provider's structured-output schema (`planning/agents.py:204`). The model is
therefore never told the required section keys or the required card count. Its
output is then validated strictly against `SectionPlan`
(`extra="forbid"`, requires `id`) at `planning/bridge.py:260`. Observed violations:
`slot_id` instead of `id` (422), and wrong card count (409, three times). There is
no repair or re-ask loop on this stage.

**E2 (would stop the next stage).** The pre-existing queued generation
`890c7cb8-…` was claimed by the native worker at startup and failed at
`planning_forms` after 2 internal retries, on a provider 400 from
`deepseek-v4-flash`: *"Invalid assistant message: content or tool_calls must be
set"* — a thinking-enabled response with empty assistant content being replayed
into the next request. Fixing E1 alone would very likely surface E2 immediately.

Full detail, including exact errors and file/line references, is in
`03-error-log.md`.

## Architecture checks

Each is reported strictly on what was observed. "Could not verify" means the code
path never ran — it is not a pass.

```text
Teaching approval blocked downstream:   could not verify
Approval returned queued asynchronously: could not verify
Worker claimed queued work:              confirmed (on a pre-existing job, not this run's)
DB-first assembly:                       could not verify
Reload/hash verification:                could not verify
Visual readiness respected:              could not verify
Native LectioDocumentV2:                 could not verify
Legacy resume_stage2 observed:           not observed
Fixture use observed:                    not observed
```

Two of these deserve a note:

* **Worker claimed queued work — confirmed.** The only positive native-execution
  evidence in the run. Worker `native-241781c19489` started cleanly and claimed a
  queued job within ~2.5 minutes. The claim loop works; what runs inside it (E2)
  does not.
* **Legacy `resume_stage2` / fixture use — "not observed" is weak evidence here.**
  No run got far enough for a legacy path or a fixture to be reachable. This is not
  a clean bill of health.

## Evidence capture script

The prescribed commands could not be run:

```powershell
uv run python scripts/capture_whole_lesson_evidence.py <science-id> --run browser-smoke-science
uv run python scripts/capture_whole_lesson_evidence.py <economics-id> --run browser-smoke-economics
```

Two reasons, both recorded rather than worked around:

1. **No generation ID exists.** The script takes a `generation_id` positional
   argument and reads that generation's persisted state. Zero generations were
   created (confirmed by direct query). There is nothing to capture.
2. **The `--run` values in the brief are not accepted by the script.** Its actual
   choices are `{run-01-science, run-02-mathematics, run-03-economics, run-04-english}`.
   `browser-smoke-science` and `browser-smoke-economics` would be rejected by
   argparse even with a valid ID.

Exit status: not run (blocked), for both lessons.

## PDF check

Not attempted. PDF export requires a `ready` document and neither run produced one.
This is **not** an export failure and must not be counted as one — it is downstream
of the actual blocker. `PDF_EXPORT_ENABLED` and `PDF_RENDER_BASE_URL` are configured
in the backend `.env`, so the export path may well be healthy; it is simply
untested. No PDF browser dependencies were installed.

## Screenshots

The in-app browser tool renders screenshots into the session transcript but does not
write image files to disk, so `screenshots/` is empty. To keep the evidence
self-contained, the visual state at each checkpoint is transcribed verbatim as page
text in `01-science-timeline.md` and `02-economics-timeline.md` — including the two
error banners, which are quoted exactly as the UI rendered them.

## Constraints honoured

```text
Source code modified during the runs:        no
Database rows edited:                        no (alembic_version verified unchanged)
Manual status changes:                       no
Fabricated visual callbacks:                 no
Approval gates bypassed:                     no
Fixtures / API-only shortcuts used:          no
Backend deliberately restarted mid-run:      no
Retries taken:                               exactly one product retry per run
Repeated replacement generations until pass: no
Playwright / Chromium / browser deps installed: no
Commits made:                                no
```

The only configuration change was the `RUN_MIGRATIONS_ON_STARTUP=false` environment
variable needed to start the backend at all (E3), applied after verifying the live
schema already satisfies every ORM table and column at HEAD.

## Smallest concrete blockers

In the order they must be cleared:

1. **Enforce the structural planner's output contract.** Replace
   `cards: list[dict]` / `sections: list[dict]` in `PathStructuralPlan`
   (`planning/models.py:383`) with typed models — sections carrying `id`, and cards
   constrained to exactly one. This is the single change that unblocks both runs.
2. **Fix the form planner's DeepSeek message replay** (`form_agent.py`), so a
   thinking-only assistant message is not sent back with empty `content`. Expect to
   hit this the moment blocker 1 is cleared.
3. **Reconcile the alembic state** — commit the missing `20260806_0032` migration or
   stamp back to `20260803_0031` — so the backend starts without an override, and
   consider a startup guard that says "database is ahead of this checkout" instead
   of exiting 3 silently.

Blockers 1 and 2 are independent; both must be fixed before a native whole-lesson
run can be expected to reach `ready`.

## Verdict

The two-lesson native browser path is **not operational** at
`bb56f8997a1a4a0a28645c2f92820bd5dcf8afd7`.

The teacher-facing front half — unit creation, readback, path planning, assumption
resolution, path approval, lesson selection, and lesson-shape control — worked
correctly and repeatably across both subjects. The native execution half was never
reached. Given E2, clearing the structural-plan blocker alone will not produce a
passing run.

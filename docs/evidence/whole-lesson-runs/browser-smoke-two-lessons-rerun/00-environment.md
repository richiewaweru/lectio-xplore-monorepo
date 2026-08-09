# 00 — Environment (rerun)

## Baseline

| Item | Value |
|---|---|
| Repository | `richiewaweru/lectio-xplore-monorepo` |
| Branch | `pageobject-integration` |
| Starting commit | `bb56f8997a1a4a0a28645c2f92820bd5dcf8afd7` |
| Commit message | `fix(native-execution): close visual callback invariants` |
| Matches expected | YES |
| Working tree at start | Clean except untracked `.tmp-xplore-native-phase02-pack/` and the previous run's evidence |
| Prior evidence | `docs/evidence/whole-lesson-runs/browser-smoke-two-lessons/` preserved, unmodified |

`git pull` was not run: HEAD already equalled the expected commit, and pulling
could have moved the baseline mid-task.

## Servers

| Item | Value |
|---|---|
| Backend | `uv run uvicorn app:app --host 127.0.0.1 --port 8000`, no `--reload` |
| Migrations at startup | **Enabled** — the previous run's `RUN_MIGRATIONS_ON_STARTUP=false` workaround is gone |
| Frontend | vite 7.3.6 on `http://localhost:5173` (`--strictPort`) |
| Browser origin | `localhost`, not `127.0.0.1`, for the OAuth origin |
| Authentication | Pre-existing session (user "richard"); no interactive sign-in needed |

`.env` already contained `RUN_MIGRATIONS_ON_STARTUP=true`; the earlier workaround
had been a process environment variable only, and it was dropped for this run.

## Environment variable presence (names only — no values read out)

Backend: `DATABASE_URL`, `GOOGLE_CLIENT_ID`, `XPLORE_PAGE_DOCUMENTS_ENABLED`,
`PDF_RENDER_BASE_URL` present. `XPLORE_V2_ENABLED` is absent but defaults to
`True` (`core/config.py:145`). Provider keys present: `ANTHROPIC_API_KEY`,
`OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `XAI_API_KEY`, `GROQ_API_KEY`.

Frontend: `PUBLIC_API_URL`, `VITE_GOOGLE_CLIENT_ID` present.

## Model routing actually in effect

This matters for interpreting the node-policy fix. `.env` overrides every slot to
DeepSeek:

```text
V3_FAST_PROVIDER=openai_compatible   V3_FAST_MODEL_NAME=deepseek-v4-flash
V3_STANDARD_PROVIDER=openai_compatible  V3_STANDARD_MODEL_NAME=deepseek-v4-pro
V3_PREMIUM_PROVIDER=openai_compatible   V3_PREMIUM_MODEL_NAME=deepseek-v4-pro
```

So `V2_FORM_PLANNER` (FAST) runs `deepseek-v4-flash` and
`V2_PATH_STRUCTURAL_PLANNER` (STANDARD) runs `deepseek-v4-pro`. Both are on the
`PromptedOutput` path (`v3_execution/llm_helpers.py:27`), which is what made the
in-library retry replay fatal. Against the shipped Anthropic defaults none of this
would apply.

## Alembic state

| Item | Value |
|---|---|
| Head before | `20260803_0031` (single head) |
| Database stamp | `20260806_0032` — a revision present in no file, commit, branch, stash, or dangling object |
| Resolution | Explicit no-op reconciliation migration `20260806_0032_reconcile_lost_revision.py`, `down_revision = "20260803_0031"` |
| Head after | `20260806_0032` (single head) |
| Backward stamping | **None.** `alembic_version` was never edited. |

Proof on a disposable database. Correction to an earlier note of mine: this scratch
database was created on the **same hosted remote server** as `DATABASE_URL`
(database name `railway`), not on a local Postgres. It was created for the proof
and dropped immediately after. The application database was never used for
migration experiments.

```text
created scratch database lectio_migration_proof
INFO  [alembic.runtime.migration] Running upgrade 20260803_0031 -> 20260806_0032,
      reconcile development databases already stamped 20260806_0032
alembic upgrade head: OK
scratch alembic_version = ['20260806_0032']
scratch table count = 30
RESULT: PASS
dropped scratch database lectio_migration_proof
```

Proof against the real database: the backend now starts with migrations enabled.
The log shows alembic running to completion with no `CommandError`, and
`/health` returns 200 for a fresh instance.

## Pre-existing state that is NOT part of this run

Four generations sit at `awaiting_teaching_approval`, created 2026-08-05:

```text
ebebdd9a-a14a-4f0e-9ac0-dd43bcc4f842
208f45d5-fd2c-4d7b-8f3b-18c3dc895d92
56331eb7-72de-4cd7-9d3c-9affbbd91fa9
030c6461-5b2d-4d2f-9f9f-3603fb88adc7
```

**No generation is in `queued` state.** The native worker claims `queued` work, so
these four are gated behind a human approval and cannot be claimed or pollute the
run's timings. Nothing was cancelled, archived, or edited — the check was
read-only, and no supported-path cleanup was necessary.

The generation that failed at `planning_forms` during the previous run
(`890c7cb8-…`) is now terminal and likewise not claimable.

## Secret handling

No secret values appear in this evidence set. `GCS_SERVICE_ACCOUNT_JSON` remains
stored in the backend `.env` as inline multi-line JSON containing a raw private
key; rotation was explicitly out of scope for this task and was not attempted.

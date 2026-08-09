# 00 — Environment

Browser-first two-lesson native E2E run.

## Baseline

| Item | Value |
|---|---|
| Repository | `richiewaweru/lectio-xplore-monorepo` |
| Git branch | `pageobject-integration` |
| Git commit | `bb56f8997a1a4a0a28645c2f92820bd5dcf8afd7` |
| Commit message | `fix(native-execution): close visual callback invariants` |
| Commit date | 2026-08-06 07:43:50 +0300 |
| Expected commit match | YES |
| Working tree | Clean except untracked `.tmp-xplore-native-phase02-pack/` (pre-existing, untouched) |
| `git pull` | Not run — HEAD already equals the expected commit; pulling could have moved the baseline |

## Preflight record

```text
Git branch:            pageobject-integration
Git commit:            bb56f8997a1a4a0a28645c2f92820bd5dcf8afd7
Backend health:        200 OK (/health, instance restarted at 2026-08-06T05:24:24Z)
Frontend reachable:    YES — http://localhost:5173 (vite 7.3.6)
Prompt verification:   PASS — prompt_checksums=ok, exit 0
Database reachable:    YES — PostgreSQL, 31 tables
Native worker started: YES — worker_id=native-241781c19489
Authentication usable: YES — pre-existing session (user "richard"), no OAuth interaction needed
Preflight start:       2026-08-06 08:12 +03:00
Preflight complete:    2026-08-06 08:28 +03:00
```

## Environment variable presence (names only; no values read out)

Backend `apps/textbook-agent/backend/.env`:

| Name | Present |
|---|---|
| `DATABASE_URL` | yes |
| `GOOGLE_CLIENT_ID` | yes |
| `XPLORE_V2_ENABLED` | **no** — not set; `core/config.py:145` defaults it to `True`, so V2 is enabled |
| `XPLORE_PAGE_DOCUMENTS_ENABLED` | yes |
| `PDF_RENDER_BASE_URL` | yes |
| Model-provider keys | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `XAI_API_KEY`, `GROQ_API_KEY` present |

Frontend `apps/textbook-agent/frontend/.env`:

| Name | Present |
|---|---|
| `PUBLIC_API_URL` | yes |
| `VITE_GOOGLE_CLIENT_ID` | yes |

All observed outbound model traffic went to `api.deepseek.com` (the configured
`V3_*` / page-lesson provider tier), not to Anthropic or OpenAI.

## Deviations from the prescribed startup procedure

Three deviations were required to get a server up. All are recorded here rather
than hidden, and none of them touch source code or lesson data.

### D1 — Stale servers were occupying both ports

* Port 8000 was held by a `python` process (PID 6052) started **2026-08-05 20:31**,
  i.e. running code from *before* HEAD (committed 2026-08-06 07:43).
* Port 5173 was held by a `node` process (PID 22056) started **2026-08-05 11:39**.

Both were stopped so that the run would exercise the current commit. Without this,
the browser would have been driving yesterday's build.

### D2 — `RUN_MIGRATIONS_ON_STARTUP=false` (blocking; see below)

The backend refused to start with exit code 3. Root cause:

```text
alembic.util.exc.CommandError: Can't locate revision identified by '20260806_0032'
```

The database's `alembic_version` table is stamped at `20260806_0032`. That revision
exists in **no file and no branch** in this repository — the latest migration on
disk is `20260803_0031_add_generation_steps.py`. It was applied by a migration file
that was subsequently deleted or never committed.

Before working around it, the live schema was compared against the ORM metadata at
HEAD:

```text
model_tables: 29   db_tables: 31
SCHEMA_OK: every ORM table/column exists in the database
```

Every table and column the HEAD code expects is present; the database is a strict
superset. So the schema is compatible and only the alembic *stamp* is phantom.

The backend was therefore started with `RUN_MIGRATIONS_ON_STARTUP=false`. This is a
runtime environment variable only:

* no source file was modified;
* no database row was edited, and in particular `alembic_version` was **not**
  re-stamped;
* no schema change was applied.

This is a real repository defect and is carried into the final report, not treated
as an incidental setup step.

### D3 — `npm ci` skipped

`frontend/node_modules` was already populated, and the dev server built and served
successfully from it (`VITE v7.3.6 ready`). `npm ci` was not re-run.

## Pre-existing state that is NOT part of this run

At startup the native worker immediately claimed a **queued generation left over
from a previous session**, `890c7cb8-5ccb-4b31-adbb-fb336b766e14`. It was not
created by this run. It is reported because it independently exercised the worker
path and failed — see `03-error-log.md`.

The `/units` list also already contained two APPROVED
"Explain why plants need light to make food" Grade 4 units from earlier sessions.
The units created by this run are identified by ID in the per-run timelines.

## Secret handling note

No secret values are reproduced in this evidence set. One incidental exposure is
recorded for the repository owner's awareness: `GCS_SERVICE_ACCOUNT_JSON` is stored
in the backend `.env` as inline multi-line JSON containing a raw private key, which
makes it trivially leakable by ordinary key-name inspection of that file. Rotation
is advisable. The key material is not reproduced here.

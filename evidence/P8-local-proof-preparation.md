# P8 — Local proof preparation

Status: P7 accepted (PASS). P8 live walkthrough is complete and ready for Sol review. Docker PostgreSQL and native backend/frontend are running. The authenticated browser approved a verified Teaching Plan, recovered two interrupted Learn outputs, and completed a third explicit retry. Learn and Print both rendered ready and remained ready after refresh.

## Local environment inspection

No `.env` values or provider credentials were printed. The three app environment files exist (`apps/textbook-agent/.env`, `backend/.env`, and `frontend/.env`). Sanitized inspection shows the backend database target is local PostgreSQL at `127.0.0.1:5432`; local frontend API configuration points to `localhost`. The root-level environment has a nonlocal database target, so it is not the native backend config and will not be used for this proof.

Available native setup:

- `uv 0.10.9`, Python virtual environment, and backend `uvicorn` executable are present.
- Node `v23.5.0`, npm `11.4.2`, `npx`, and installed frontend dependencies are present.
- `uv run alembic heads` reports `20260913_0042 (head)`.
- `uv run python -c "import sys; sys.path.insert(0, 'src'); import app; print('backend import: ok')"` succeeds.
- Backend startup applies Alembic migrations in the app lifespan (`settings.run_migrations_on_startup` defaults true).
- `docker compose --profile dev config --services` resolves `db`, `backend`, `db-dev`, and `frontend`; P8 will start only `db-dev` as required by the local runbook.
- Ports 5432, 8000, and 5173 were closed at inspection time.

Docker readiness:

- Docker CLI is installed at `C:\Program Files\Docker\Docker\resources\bin\docker.exe`.
- Windows service `com.docker.service` is `Stopped`, start type `Manual`.
- `docker info --format '{{.ServerVersion}}'` emitted no output or exit status after approximately 15 seconds; it was interrupted. No Docker command has started or modified a container or volume.
- Parent reports Docker Desktop start/elevation was requested asynchronously. Recheck `docker info` after that external state changes.
- Sanitized comparison found app-root Compose `POSTGRES_USER`/`POSTGRES_PASSWORD` differ from the credentials in `backend/.env`; database name and port match. Starting `db-dev` with the root `.env` as-is would make a new database reject native backend connections. Do not print or overwrite either env file. Before starting, inspect existing `db-dev` container and volume. For a new volume, pass values parsed from backend `DATABASE_URL` as process-scoped `POSTGRES_*` variables without echoing them. For an existing volume, check which local role works; never delete/reset the volume.

## Live proof progress — 2026-09-23

The P8 environment is now available. The parent task reports healthy PostgreSQL container `textbook-agent-db-1` on local port 5432 and successful connection from the native backend using the existing `backend/.env`. Native API and Vite are running on 127.0.0.1:8000 and 127.0.0.1:5173. No database volume was deleted or reset, and no environment file was changed.

Clean Unit/lesson identifiers from the active authenticated browser: Unit `c85de318-1c08-40aa-9237-3432e377732f`; lesson `ad945ebb-c754-48b2-8fbe-a9e9cf5c3264`; path version `7cfbde4e-b360-4da5-b3f9-db1a85109850`; preparation/generation `c88bbe41-4780-45ff-951c-a91eb98bf6ae`. The Unit path is approved/locked. A read-only PostgreSQL inspection found the preparation generation at status/stage `awaiting_teaching_approval`; nested `page_document_v2.teaching_review` is pending revision 1, with one revision and a Teaching Plan. `workspace_state_from_layers` plus `project_lesson_workspace` returns `preparation.state=awaiting_review`, `review_kind=teaching_plan`, and Learn/Print `not_created`. This proves the backend projection is consistent with persisted state.

The browser initially showed the structural “Review concepts” action. Its POST returned the structural handler's expected 409 (`Generation is not awaiting explicit approval`) because the worker had already advanced. The Plan page previously displayed that stale structural panel after the conflict. It now refreshes canonical lesson status on that specific stage conflict and hydrates the current Teaching Plan review. The regression covers stale structural state → 409 → refreshed Teaching Plan content and approval control, and passes. The delegated CUA session exposes only Chrome Work and has no IAB browser; the parent is refreshing the authenticated IAB tab before any browser success is claimed. An isolated Playwright login was not used for authentication; Google OAuth origin validation failed on localhost and 127.0.0.1.

Exact validation for the P8 fix, from `apps/textbook-agent/frontend`:

```text
npm run test -- "src/routes/units/[id]/lessons/[lessonId]/plan/page.test.ts"
6 tests passed across 1 file.
npm run check
svelte-check found 0 errors and 5 existing warnings in 4 unrelated editor/canvas files.
npm run build
Passed; existing Svelte warnings and optional dependency notices were emitted.
```

## Authenticated browser walkthrough — current evidence

The parent-operated authenticated IAB reached the actual Teaching Plan review for the same lesson. Visible review metadata showed pending revision 1 and hash `b47708dba7f066ea62fec3483f291ea79b702b788eaf4148bcab624a1d91d5a2`; the pedagogical plan content was visible. The parent clicked Approve once. The page showed Approved, review revision 2, verified approved revision 1, and the same content hash. A direct PostgreSQL read confirmed the immutable revision 1 record is approved with `approval_hash_binding=submitted`; source preparation remained separate from downstream output status.

The parent clicked Create Learn once at approximately 08:47:04Z. Browser UI first showed preparing; View Learn opened `/learn` and displayed the queued/running message. Persisted realization `84bbd45c-ecad-4c05-89d7-a101be872b86` pinned Teaching Plan `a6719660-5307-4a71-9750-77b2ae5a151c`, revision 1, hash above. First output `learn-out-52ec20b706cc4e46` was owned by the signed-in user and entered running under lease token 1. Its worker heartbeat expired after the native API process was restarted at approximately 09:02:04Z. The startup reconciler changed the realization to `failed_recoverable` with `Learn execution interrupted; retry is available`, changed the old output to `failed`, cleared the worker/heartbeat, and did not retry automatically or alter the approved preparation.

After canonical lesson status refreshed, the authenticated Learn page visibly showed the recoverable interruption message and enabled Retry Learn. The parent clicked Retry Learn once. At 09:05:24Z the existing realization was advanced to realization revision 2 and bound to new output `learn-out-114e43fdfd73454d`; old output `learn-out-52ec20b706cc4e46` remains preserved. A read-only PostgreSQL check confirmed the new output is owned by the same user and pinned to the same approved plan/revision/hash; it entered `running` with worker `learn-18c698e4e68d`, lease token 1, 600-second lease, claimed at 09:05:25.085614Z, and heartbeat at 09:06:28.081131Z. Browser UI showed “Learn is being created.” No duplicate Create or Retry was submitted.

The parent then created Print once while the Learn retry remained running. PostgreSQL shows the independent Print realization `e6d86049-193a-4eb2-a330-fba603189e40`, revision 1, output `cf88fb9a-2ab0-49d6-8514-74afc6f4e0bf`, pinned to the same approved Teaching Plan revision/hash. The output belongs to the signed-in user, has a `document_json` envelope and persisted page-document state, and reached `ready`. After restarting only Vite with the same API-target override to recover slow IAB navigation, the authenticated browser opened `/print` and rendered the ready preview. The visible header was `Approved Learn · preparing Print · ready`; the Edit link targeted `/studio/print/cf88fb9a-2ab0-49d6-8514-74afc6f4e0bf`, and Download PDF was available. The visible document included orient, recall, explain, contrast tasks, a check, and answer key. No duplicate Print admission occurred.

Immediately after an earlier backend restart, one status refresh briefly returned Internal Server Error and a full navigation showed `Loading session…`; once canonical state loaded, the visible retry card matched the DB. `Loading session…` was the frontend auth bootstrap waiting for `GET /api/v1/auth/me`; no auth token was copied or inspected. Vite had high CPU/memory use and IAB navigation timed out; restarting only the frontend (keeping API target and backend/DB intact) restored navigation.

No controlled failure injection was added to production. The live retry above is a real process-interruption recovery, with a preserved old output and a distinct new retry output.

### P8 live worker-commit defect and recovery — 2026-09-23

The first and second Learn attempts (`learn-out-52ec20b706cc4e46` and `learn-out-114e43fdfd73454d`) expired after process restarts and startup reconciliation safely parked them as `failed_recoverable`; each old output was preserved. The second output had 15 durable ready checkpoints and a fresh heartbeat while running. Inspection found `LearnRealizationWorker._loop` runs each job in a short-lived `AsyncSession` but did not commit the successful producer's flushed document, realization, and editable lesson. Closing the session rolled the final state back, leaving a running row after heartbeats stopped and causing later lease recovery.

The worker now commits successful finalization before its per-job session closes. Escaped post-production exceptions are caught, logged with typed finalization metadata, and parked as recoverable only if output owner, pinned approval identity, and the current lease verify. A stale/lost lease cannot write failure state; corrupt or foreign outputs are not mutated. A disposable-session regression checks ready completion from a fresh DB session. An injected post-production publication-validation failure checks recoverable parking, preservation of source approval, and absence of an editable lesson.

After a controlled backend restart with the fix, the parent clicked Retry Learn once from the existing recoverable UI. The new output `learn-out-6603dafebcb14015` completed as realization revision 3 (`ready`) and Generation (`completed`) under worker `learn-97c8760c78d2`. PostgreSQL confirms nonempty document content and owner-linked editable lesson `84c64909-ff6c-468d-85ff-2d6080247271`, whose `source_generation_id` is exactly the new output. It remains pinned to Teaching Plan revision 1 and hash `b47708dba7f066ea62fec3483f291ea79b702b788eaf4148bcab624a1d91d5a2`. The preparation remains approved, and Print remains ready on the original detached output. The authenticated Learn UI rendered the 17-node document, three interactions, and Edit link `/builder/84c64909-ff6c-468d-85ff-2d6080247271`. The parent selected the correct misconception radio option and received correct Check feedback; the page labels attempts as preview-only and unsaved. After refresh, Learn remained ready and the attempt reset, as expected. The separate Print tab also refreshed and still rendered ready with the same Studio output link and Download PDF. Both output states remained ready after refresh with no visible UI errors.

Focused verification from `apps/textbook-agent/backend`:

```text
uv run pytest tests/application/test_p04_learn_worker.py -q
16 passed, 1 existing Pydantic warning, 59.50s.

uv run ruff check src/learn/generation/worker.py tests/application/test_p04_learn_worker.py
All checks passed.

uv run python ../tools/agent/check_architecture.py --format text
No architecture violations found.
```

From `apps/textbook-agent/frontend`:

```text
npm test -- 'src/routes/units/[id]/lessons/[lessonId]/plan/page.test.ts'
6 passed in 57.50s.
```

## Existing auth and clean lesson path

The local app exposes Google OAuth (`POST /api/v1/auth/google`); source inspection found no development bypass credential. The configured client ID is present but was not read or printed. The browser walkthrough therefore uses the app's existing Google sign-in and normal Unit flow, without manufacturing an auth token or user.

The Units page's normal create flow calls `constructorReadback`, then `createUnit`, then `planUnitPath`, and navigates to the created Unit. After login, create a new Unit with a distinctive topic/title such as `P8 stability walkthrough 2026-09-23`; this creates a clean Unit Path and lesson rather than relying on historical legacy generations. If the account cannot create/approve a Unit Path, record that as the live blocker rather than mutating old records.

There is no browser test-account credential in the repository: route tests install `get_current_user` overrides in-process, while the live login page invokes Google Identity Services and exchanges a real credential. An existing signed-in Google account/OAuth authorization is therefore required for the walkthrough; no account or token was manufactured.

## Controlled recovery assessment

The deterministic P7 failure fixtures patch provider boundaries inside pytest and do not provide a running-app failure switch. Model resolution supports per-node environment overrides (provider, model name, base URL, and API-key variable), which could route one node to an ephemeral OpenAI-compatible local responder without editing product code. That responder has not been validated against the full preparation/Learn authoring output contracts; avoid changing the existing `.env` or claiming live recovery until a safe one-shot responder has been proven. If no supported ephemeral fixture can exercise the browser retry safely, retain P7's deterministic failure evidence and mark the live failure walk not run.

## Prepared native commands

Run these only after the Docker daemon is responsive. First inspect `docker compose ps -a db-dev` and the project volume list. Do not assume `POSTGRES_*` changes affect an already initialized PostgreSQL volume.

From `apps/textbook-agent/`:

```powershell
$line = Get-Content backend/.env | Where-Object { $_ -match '^\s*DATABASE_URL\s*=' } | Select-Object -First 1
$url = ($line -split '=', 2)[1].Trim().Trim('"').Trim("'") -replace '^postgresql\+asyncpg://', 'postgresql://'
$db = [uri]$url
$credentials = $db.UserInfo.Split(':', 2)
$env:POSTGRES_USER = [uri]::UnescapeDataString($credentials[0])
$env:POSTGRES_PASSWORD = [uri]::UnescapeDataString($credentials[1])
$env:POSTGRES_DB = $db.AbsolutePath.TrimStart('/')
$env:DB_PORT = [string]$db.Port
docker compose --profile dev up -d db-dev
docker compose ps
Remove-Item Env:POSTGRES_USER,Env:POSTGRES_PASSWORD,Env:POSTGRES_DB,Env:DB_PORT -ErrorAction SilentlyContinue
```

The wrapper reads the backend URL without displaying it and scopes overrides to the compose process. Use those init overrides only when the volume is new. If a `db-dev` volume/container already exists, test local roles without printing passwords; if its existing role does not match, prefer a reversible native backend `DATABASE_URL` process override for that existing role. Confirm `db-dev` is healthy and bound to local port 5432. Do not use `docker compose up --build`; do not remove or reset the persistent volume.

From `apps/textbook-agent/backend/`:

```powershell
uv run uvicorn app:app --reload --app-dir src --host 127.0.0.1 --port 8000
```

Confirm `http://127.0.0.1:8000/health` responds healthy and that app startup completes migrations. Capture logs without copying credentials.

From `apps/textbook-agent/frontend/`:

```powershell
npm run dev -- --host 127.0.0.1 --port 5173
```

Open the ordinary app route using the local origin that matches configured Google OAuth origins. `npx` and the Playwright skill wrapper are available for the live browser walkthrough; no browser automation or OAuth attempt has been made before the app is running.

## Walkthrough sequence

1. Sign in through Google OAuth and create the new Unit/Path above.
2. Open the approved Unit Path and select a new lesson; record unit/path/lesson IDs.
3. Prepare the lesson, observe planning, review the structural gate if shown, and verify the actual Teaching Plan content.
4. Approve, refresh, and verify the same approved Teaching Plan revision/hash.
5. Create Learn; record realization/output IDs and timings, observe queued/running/ready, open the editable output, and exercise an interaction if present.
6. Return to Plan and create Print; record its distinct realization/output IDs and timings, observe independent status, open preview, refresh, and verify Learn remains ready.
7. Record browser console/network errors and final canonical states.
8. If a deterministic recoverable failure can be induced with an existing local test fixture without adding a persistent product hook or risking the approved plan, prove parked failure, unchanged approval/healthy sibling, UI polling stop, and explicit retry. Otherwise retain P7's deterministic failure evidence and report the live recovery walk as not run.

## Exact preparation checks

From `apps/textbook-agent/backend/`:

```text
uv run alembic heads
20260913_0042 (head)

uv run python -c "import sys; sys.path.insert(0, 'src'); import app; print('backend import: ok')"
backend import: ok
```

From `apps/textbook-agent/`:

```text
docker compose --profile dev config --services
db
backend
db-dev
frontend

docker info --format '{{.ServerVersion}}'
No output after ~15 seconds; interrupted because daemon did not answer.
```

At the initial check, ports 5432, 8000, and 5173 were closed. Docker `com.docker.service` was Stopped/Manual. The native frontend was subsequently started on 127.0.0.1:5173. The in-app browser opened `http://127.0.0.1:5173/units` and displayed `NATIVE WORKSPACE UNAVAILABLE` with an Internal Server Error because the backend/database were not running. The browser tab was retained for handoff. No lesson creation or recovery flow has run. An elevated Docker Desktop launch was attempted, but the service remained stopped, and Docker did not answer its readiness check. No product files or environment files were modified during preparation.

When the browser flow runs, record screenshot/trace artifacts under the existing `output/playwright/` folder and query the CLI `console` and `network` views after each significant state transition. Record preparation generation ID, Teaching Plan ID/revision/hash, Learn realization/output IDs, Print realization/output IDs, timestamps/durations, retry counts, final statuses, and any browser/network errors in this evidence file.

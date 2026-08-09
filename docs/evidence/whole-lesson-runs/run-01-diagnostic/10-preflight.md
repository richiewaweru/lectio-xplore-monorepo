# Preflight — Run 01 diagnostic

Backend started **without `--reload`**, unbuffered, logs captured to `logs/backend.log`.
Instance `6d75bff8-4d85-4985-a9a1-a084308c021a`, started `2026-08-07T15:04:42Z`,
architecture `shell-pipeline-native-lectio`.

| Check | Result | Latency | Evidence | Notes |
|---|---|---|---|---|
| Docker Postgres healthy | PASS | — | `db/00-DOCKER_DB_IDENTITY_PROOF.md` | `textbookagent-db-1`, PG 16.9 |
| Backend == Docker DB | PASS | — | same | identical `system_identifier` + postmaster start |
| Migrations current | PASS | — | `alembic current` | `20260806_0032 (head)` == heads |
| `GET /health` | 200 | 0.023 s | `http/preflight-health.json` | liveness |
| `GET /health/ready` | 200 | 0.277 s warm | `http/preflight-health-ready.json` | see cold-start note |
| `GET /health/deep` | 200 | 0.024 s | `http/preflight-health-deep.json` | same handler as ready |
| Frontend `localhost:5173` | 200 | 0.242 s | — | Vite v7.3.6, strict port |
| Proxy `/api/v1/units` unauth | 401 | 0.220 s | — | expected before sign-in |
| Prompt checksums | PASS | — | `verify_whole_lesson_prompts.py` | `prompt_checksums=ok` |
| Focused planning tests | PASS | 0.72 s | — | 10 passed |
| Architecture guard | PASS | — | — | no violations |
| Browser console | clean | — | — | only the three expected 401s |
| Native worker running | PASS | — | `logs/backend.log` | `worker_id=native-8e7a515660c3` |

## Readiness dependency latencies (warm)

| Dependency | Status | Latency |
|---|---|---|
| postgres | ok | 53.2 ms |
| event_bus | ok | — |
| playwright | ok | 1771.9 ms |
| pdf_temp_dir | ok | 2.0 ms |

**Cold-start note.** The very first `/health/ready` after boot took **20.03 s**; every
later call took 0.28–1.8 s. `/health` was 5 ms at the same moment, so the app was
serving. The cost is the Playwright/Chromium launch inside `_check_playwright_runtime`
(`src/core/health/routes.py:133`) on a cold browser cache. Worth knowing because the
same cold Chromium launch will be paid again by the first PDF export.

## Frontend → backend wiring

`frontend/.env` sets `PUBLIC_API_URL=http://localhost:8000`, but in dev the browser
calls same-origin `http://localhost:5173/api/v1/*` and Vite proxies to the backend.
Confirmed in the network log: `GET http://localhost:5173/api/v1/units -> 401`. No CORS
errors, no calls to any remote host, no Railway traffic.

## Generation summary at preflight

`running=0, pending=0, failed_last_hour=0, completed_last_hour=0` — clean baseline, so
anything observed during this run is attributable to it.

---

## Uptime-degradation watch — previous run's blocker 1 did NOT recur

The previous run (`browser-smoke-two-lessons-rerun/07-final-report.md`) reported as its
number-one blocker: *"Backend degrades to all-500s after minutes of uptime … clears on
restart"*, which is what stopped that run. Two hypotheses were tested and rejected there
(server idle timeouts; NAT dropping idle TCP).

A `/health` probe ran every 30 s for the whole of this diagnostic.

```
total samples:      121   (~60 minutes of coverage)
non-200 responses:  4
```

All four non-200s are accounted for and none is a degradation:

```
2026-08-07T15:17:34Z 000   <- my controlled restart (single-instance cleanup)
2026-08-07T15:18:07Z 000   <- my controlled restart
2026-08-07T15:20:12Z 000   <- my controlled restart (guarded runner)
2026-08-07T16:00:26Z 000   <- my controlled restart (validator fix)
```

Between restarts the backend served **every** probe with `200`, including a continuous
stretch from 15:20 to 16:00 that spans the entire generation run.

**Interpretation.** The one material difference from the previous run is the database
path: that run used Railway Postgres over `interchange.proxy.rlwy.net`, this run used
local Docker Postgres over loopback. The degradation did not reproduce even once. That is
consistent with the cause being the remote proxy connection path rather than the
application's pool handling — `pool_pre_ping=True` and `pool_recycle=300` are unchanged
between the two runs.

This is evidence, not proof: it is a negative result over one hour on a different DB
path. But it does mean **blocker 1 should not be treated as an open application bug**
until it is reproduced against local Postgres.

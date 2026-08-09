# Docker Postgres identity proof — Run 01 diagnostic

**Captured:** 2026-08-07
**Verdict: BACKEND CONNECTED TO DOCKER POSTGRES — YES**

## Container

| Property | Value |
|---|---|
| Container | `textbookagent-db-1` |
| Image | `postgres:16-alpine` (PostgreSQL 16.9) |
| Compose project | `textbookagent`, service `db` |
| Compose working dir | `C:\Projects\Textbook agent` (legacy repo dir — see note) |
| Volume | `textbookagent_pgdata` -> `/var/lib/postgresql/data` |
| Host port | `127.0.0.1:5432` |
| Container IP | `172.20.0.4` |
| Health | `127.0.0.1:5432 - accepting connections` |

**Note on `db-dev`:** the brief asked for the `db-dev` profile service. `db-dev` has
never been started in this environment — no `pgdata_dev` volume exists — and it binds
the same host port `5432` as the already-running `db`, so the two cannot coexist.
Per user decision, this run uses the running `db` service. It is the same image,
the same local Docker Postgres 16, and the same host port that `backend/.env` already
targets. The requirement that matters — local Docker rather than Railway — is met.

## Two-sided identity, both over TCP

Executed against the Docker container directly with `psql -h 127.0.0.1`, and against
the application's own `create_async_engine` / `async_session_factory`
(`src/core/database/session.py:21`) in the app's `uv` environment.

| Field | Docker side (`psql`) | App side (SQLAlchemy) | Agree |
|---|---|---|---|
| `current_database()` | `textbook_agent` | `textbook_agent` | yes |
| `current_user` | `textbook` | `textbook` | yes |
| `inet_server_addr()` | `127.0.0.1` | `172.20.0.4/32` | see below |
| `inet_server_port()` | `5432` | `5432` | yes |
| `pg_backend_pid()` | `27326` | `27390` | distinct, as expected |
| `version()` | PostgreSQL 16.9 (Alpine) | PostgreSQL 16.9 (Alpine) | yes |
| `system_identifier` | `7624095893609250850` | `7624095893609250850` | **yes** |
| `pg_postmaster_start_time()` | `2026-08-07 06:49:40.520061+00` | `2026-08-07 06:49:40.520061+00` | **yes** |

`inet_server_addr()` differs by design, not by identity: the psql session originates
inside the container and lands on loopback `127.0.0.1`, while the app connects from the
host through the published port and lands on the container's bridge address
`172.20.0.4` — which matches `docker inspect`. The two backend PIDs differ because they
are two separate live connections to one server.

**The decisive evidence is `system_identifier` + `pg_postmaster_start_time()`.** These
are per-cluster values written at initdb and at process start. Identical values on both
sides prove the application engine and the Docker container are the *same PostgreSQL
instance*, not two servers with matching names.

## DATABASE_URL

```
DATABASE_URL          = postgresql+asyncpg://***:***@127.0.0.1:5432/textbook_agent   <- in use
DATABASE_URL_RAILWAY  = postgresql+asyncpg://***:***@interchange.proxy.rlwy.net:16492/railway   <- present but UNUSED
```

`settings.database_url` and the live engine URL both resolve to `127.0.0.1:5432`.
`DATABASE_URL_RAILWAY` is a separate key that nothing reads. **Railway is not in use
for this run.**

## Migrations

```
alembic current : 20260806_0032 (head)
alembic heads   : 20260806_0032
```

Migrations are current.

## Raw captures

* `01-docker-side-identity.txt`
* `02-app-side-identity.txt`

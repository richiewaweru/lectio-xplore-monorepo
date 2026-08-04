# Development Workflow

## How Agents Work on This Project

1. Read `agents/ENTRY.md` (the universal entry point).
2. Read `agents/project.md` (this project's specific rules).
3. Pick the right workflow from `agents/workflows/`.
4. Follow the workflow's tracking checklist.
5. Run validation before marking work complete.

## CI Required Checks

| Check | What it validates |
| --- | --- |
| `backend-quality` | Ruff lint + pytest |
| `frontend-quality` | Svelte type-check + build |

These are the only required PR checks. The merge gate is intentionally minimal and code-focused.

Project-local validation uses `python tools/agent/validate_repo.py --scope all`, which now covers backend, frontend, and tooling automation tests declared in `docs/project/context-summary.yaml`.

Additional high-signal checks remain available for local verification, release prep, and operator handoffs, but they are not merge blockers:

- `python tools/agent/check_architecture.py --format text`
- `python tools/agent/validate_repo.py --scope tooling`
- `cd frontend && npm run test`
- `python scripts/smoke_test.py <base-url>`

## Deployment

Deployment remains manual for now. GitHub Actions is no longer the source of truth for release or deploy validation.

- Backend deployment follows the Railway runbooks and operator notes in `docs/project/runs/`
- Frontend deployment follows the Vercel readiness handoff and operator notes
- Release prep should record any manual deploy validation in the active runbook or handoff

## Runtime Verification

Before testing textbook generation in dev:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:5173
```

Verify that:

- `/health` returns the current runtime fingerprint (`instance_id`, `started_at`, `pipeline_architecture`)
- the frontend root responds on the expected port
- the backend and frontend agree on the configured API origin before starting new generations

For Docker-based verification, use `docker compose up --build` from the repo root and confirm the `backend` and `frontend` services both report healthy.

## Execution Boundary

- `agents/` -- universal standards and workflows (portable, agent-agnostic)
- `tools/agent/` -- project-local validation scripts (reads `context-summary.yaml`)
- `backend/src/core/` -- shared infrastructure and shared auth/profile/user primitives
- `backend/src/generation/` -- generation app (HTTP, persistence, generation orchestration)
- `backend/src/planning/` -- Teacher Studio planning layer
- `backend/src/pipeline/` -- standalone generation engine
- `.github/workflows/ci.yml` -- the minimal required PR validation workflow

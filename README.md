# Lectio Xplore Monorepo

Unit-driven curriculum product: **Print** (PDF) and **Learn** (interactive) realize the same Unit path.

## Packages

| Path | Package | Role |
|---|---|---|
| `packages/lectio-page` | `@lectio/page` | Print document engine |
| `packages/lectio-learn` | `@lectio/learn` | Interactive Learn components |
| `apps/textbook-agent` | Xplore app | FastAPI + SvelteKit product |

## Architecture

See [docs/architecture/CURRENT_SYSTEM.md](docs/architecture/CURRENT_SYSTEM.md).

## Common commands

```bash
pnpm page:test
pnpm page:check
pnpm app:check
pnpm program:domain-guards
```

Backend (from `apps/textbook-agent/backend`):

```bash
uv run uvicorn app:app --reload --app-dir src
```

Frontend (from `apps/textbook-agent/frontend`):

```bash
pnpm dev
```

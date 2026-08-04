# Setup Guide - v0.1.0

## Prerequisites

- **Python** 3.11+ ([python.org](https://python.org))
- **uv** (Python package manager) - Install: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
- **Node.js** 20+ ([nodejs.org](https://nodejs.org))
- **npm** (comes with Node.js)
- **Git**

## Backend Setup

```bash
cd backend

# Install all dependencies (creates .venv automatically)
uv sync --all-extras

# Copy and configure environment variables
cp .env.example .env
# Edit .env and add your API keys:
#   ANTHROPIC_API_KEY=sk-ant-...
#   OPENAI_API_KEY=sk-...

# Verify installation
uv run pytest
```

### Running the Backend

```bash
cd backend

# Development server with auto-reload
uv run uvicorn textbook_agent.interface.api.app:app --reload

# Verify health check
curl http://localhost:8000/health
# Should return: {"status":"ok","version":"0.1.0"}
```

## Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Copy environment config
cp .env.example .env

# Start development server
npm run dev
```

The frontend dev server starts at `http://localhost:5173` and proxies API requests to the backend at `http://localhost:8000`.

## Running Both Together

Open two terminals:

```bash
# Terminal 1 - Backend
cd backend && uv run uvicorn textbook_agent.interface.api.app:app --reload

# Terminal 2 - Frontend
cd frontend && npm run dev
```

## Environment Variables

### Backend (`.env`)

| Variable | Default | Description |
|---|---|---|
| `PROVIDER` | `claude` | LLM provider: `claude` or `openai` |
| `ANTHROPIC_API_KEY` | | Anthropic API key |
| `OPENAI_API_KEY` | | OpenAI API key |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Claude model ID |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model ID |
| `MAX_RETRIES` | `2` | Max retry attempts per pipeline node |
| `QUALITY_CHECK_ENABLED` | `true` | Enable quality checker node |
| `TEMPERATURE` | `0.3` | LLM temperature |
| `OUTPUT_DIR` | `outputs/` | Generated textbook output directory |
| `OUTPUT_FORMAT` | `html` | Output format |
| `GOOGLE_CLIENT_ID` | | Google OAuth client ID (from Google Cloud Console) |
| `JWT_SECRET_KEY` | auto-generated | Secret key for JWT signing |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `10080` | JWT expiry (default: 7 days) |
| `DATABASE_URL` | `sqlite+aiosqlite:///./textbook_agent.db` | Database connection URL |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | Allowed CORS origin |

### Frontend (`.env`)

| Variable | Default | Description |
|---|---|---|
| `PUBLIC_API_URL` | `http://localhost:8000` | Backend API base URL |
| `VITE_GOOGLE_CLIENT_ID` | | Google OAuth client ID (same as backend) |

## Project Structure

```
Textbook agent/
├── backend/                # FastAPI + Python (DDD architecture)
│   ├── src/textbook_agent/
│   │   ├── domain/         # Core business logic (entities, services, prompts, ports)
│   │   ├── application/    # Use cases, orchestrator, DTOs
│   │   ├── infrastructure/ # Providers, auth, database, renderer, storage
│   │   └── interface/      # FastAPI routes, middleware, dependencies
│   └── tests/              # 76 tests (domain, app, infra, interface)
├── frontend/               # SvelteKit + TypeScript
│   └── src/
│       ├── lib/            # Stores, API clients, components, types
│       └── routes/         # Pages (login, onboarding, dashboard, textbook viewer)
└── docs/                   # Project documentation
    ├── PROPOSAL_v1.0.md    # Original product specification
    └── v0.1.0/             # Current release docs (architecture, schemas, setup, workflow)
        └── progress/       # Phase handoff documents
```

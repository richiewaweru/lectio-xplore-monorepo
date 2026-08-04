# Phase 3 Handoff — Authentication, Student Profile, CLI Removal

**Date:** 2026-03-11
**Base commit:** Phase 2 complete
**Status:** Phase 3 COMPLETE — CLI removed, Google OAuth + JWT auth added, rich student profile with persistent storage, 76 tests passing, 0 lint errors

---

## What Was Done

Phase 3 transformed the application from an unauthenticated prototype into a real multi-user app with Google OAuth login, persistent student profiles, and personalized content generation.

### Implementation Summary

| Step | Component | Files Changed/Created | Status |
|------|-----------|----------------------|--------|
| 1 | CLI removal | Deleted `interface/cli/`, removed pyproject.toml entry point, updated docs | Done |
| 2 | New dependencies | `python-jose`, `google-auth`, `sqlalchemy`, `aiosqlite`, `requests` | Done |
| 3 | Settings expansion | `infrastructure/config/settings.py` — auth, DB, CORS settings | Done |
| 4 | Database layer | `infrastructure/database/{models.py,session.py}` — SQLAlchemy models + async session | Done |
| 5 | Auth infrastructure | `infrastructure/auth/{google_auth.py,jwt_handler.py}` — Google token verify + JWT | Done |
| 6 | Domain entities | `domain/entities/{user.py,student_profile.py}` — User + StudentProfile | Done |
| 7 | Value objects | `domain/value_objects/{education_level.py,learning_style.py}` — new enums | Done |
| 8 | Domain ports | `domain/ports/{user_repository.py,student_profile_repository.py}` — abstract repos | Done |
| 9 | SQL repositories | `infrastructure/repositories/{sql_user_repo.py,sql_student_profile_repo.py}` | Done |
| 10 | Auth routes | `interface/api/routes/auth.py` — POST /auth/google, GET /auth/me | Done |
| 11 | Auth middleware | `interface/api/middleware/auth_middleware.py` — JWT validation dependency | Done |
| 12 | Profile routes | `interface/api/routes/profile.py` — GET/POST/PATCH /profile | Done |
| 13 | LearnerProfile expansion | Added education_level, interests, learning_style, goals fields | Done |
| 14 | GenerationRequest slim-down | Now only subject + context + optional depth/language override | Done |
| 15 | Use case hydration | `GenerateTextbookUseCase` merges StudentProfile + request into LearnerProfile | Done |
| 16 | Prompt personalisation | Planner + content prompts inject education level, interests, learning style, goals | Done |
| 17 | Protected endpoints | All generation endpoints require auth; profile loaded before generation | Done |
| 18 | Frontend auth | Login page (Google Identity Services), auth store, token attachment | Done |
| 19 | Frontend onboarding | Multi-section profile setup form with interest tag picker | Done |
| 20 | Frontend dashboard | Profile summary, simplified generation form, progress display | Done |
| 21 | Frontend routing | Auth guard in layout, redirect to /login or /dashboard | Done |
| 22 | Tests | New auth + profile tests, updated API tests with auth overrides | Done |
| 23 | Docs | Updated ARCHITECTURE.md, SETUP.md, CLAUDE.md | Done |

### New Files Created

**Backend — Domain:**
- `domain/entities/user.py` — `User` entity
- `domain/entities/student_profile.py` — `StudentProfile` entity
- `domain/value_objects/education_level.py` — `EducationLevel` enum
- `domain/value_objects/learning_style.py` — `LearningStyle` enum
- `domain/ports/user_repository.py` — `UserRepository` abstract port
- `domain/ports/student_profile_repository.py` — `StudentProfileRepository` abstract port

**Backend — Infrastructure:**
- `infrastructure/auth/__init__.py`
- `infrastructure/auth/google_auth.py` — Google ID token verification
- `infrastructure/auth/jwt_handler.py` — JWT create/decode
- `infrastructure/database/__init__.py`
- `infrastructure/database/models.py` — SQLAlchemy table models (users, student_profiles, generations)
- `infrastructure/database/session.py` — Async engine + session factory
- `infrastructure/repositories/sql_user_repo.py` — SQLAlchemy `UserRepository`
- `infrastructure/repositories/sql_student_profile_repo.py` — SQLAlchemy `StudentProfileRepository`

**Backend — Interface:**
- `interface/api/routes/auth.py` — Auth endpoints
- `interface/api/routes/profile.py` — Profile CRUD endpoints
- `interface/api/middleware/__init__.py`
- `interface/api/middleware/auth_middleware.py` — `get_current_user` dependency

**Backend — Tests:**
- `tests/infrastructure/test_auth.py` — JWT handler tests (4 tests)
- `tests/domain/test_student_profile.py` — StudentProfile, User, enum validation (7 tests)

**Frontend:**
- `src/lib/stores/auth.ts` — Auth state management
- `src/lib/api/auth.ts` — Google token exchange API
- `src/lib/api/profile.ts` — Profile CRUD API
- `src/lib/components/ProfileSetup.svelte` — Onboarding form
- `src/routes/login/+page.svelte` — Google Sign-In page
- `src/routes/onboarding/+page.svelte` — Profile creation
- `src/routes/dashboard/+page.svelte` — Main dashboard

### Files Deleted
- `interface/cli/__init__.py`
- `interface/cli/main.py`

---

## Architecture Decisions Made During Phase 3

### 1. SQLite over PostgreSQL
Chose SQLite (via aiosqlite) for zero-config local development. The async SQLAlchemy abstraction means switching to PostgreSQL later requires only changing `DATABASE_URL`.

### 2. JWT stored in localStorage
The frontend stores the JWT in localStorage rather than httpOnly cookies. This simplifies the SPA architecture — the token is attached via `Authorization: Bearer` header. For production, httpOnly cookies would be more secure.

### 3. StudentProfile vs LearnerProfile separation
`StudentProfile` is the persistent entity stored in the DB (who the student is). `LearnerProfile` is the per-generation value object passed through the pipeline (what to generate now). The use case merges them.

### 4. GenerationRequest slimmed down
Previously `GenerationRequest` carried all learner fields (age, depth, language). Now it only carries `subject`, `context`, and optional overrides. Everything else comes from the student's profile.

### 5. Dependency overrides for testing
Tests use FastAPI's `dependency_overrides` to mock `get_current_user` and `get_student_profile_repository`, avoiding the need for a test database.

### 6. Google Identity Services (not OAuth redirect)
Used Google's one-tap / button approach rather than a server-side redirect flow. The frontend loads the GSI JavaScript library and receives the ID token directly, which it sends to the backend.

---

## Test Coverage

**Total: 76 tests, all passing**

| Module | Tests | Description |
|--------|-------|-------------|
| `tests/domain/test_entities.py` | 12 | Entity schema validation |
| `tests/domain/test_prompts.py` | 18 | Prompt builder output validation |
| `tests/domain/test_nodes.py` | 8 | Pipeline node execution with MockProvider |
| `tests/domain/test_student_profile.py` | 7 | StudentProfile, User, enum validation (NEW) |
| `tests/infrastructure/test_providers.py` | 4 | Provider factory |
| `tests/infrastructure/test_renderer.py` | 8 | HTML rendering output |
| `tests/infrastructure/test_auth.py` | 4 | JWT handler round-trip (NEW) |
| `tests/application/test_orchestrator.py` | 3 | Full pipeline with MockProvider |
| `tests/interface/test_api.py` | 6 | Health, generate (202), auth (401), status (404), poll-to-completion (UPDATED) |
| `tests/tooling/` | 6 | Architecture guard + commit tooling |

---

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Health check |
| POST | `/api/v1/auth/google` | No | Exchange Google ID token for JWT |
| GET | `/api/v1/auth/me` | Yes | Get current user |
| GET | `/api/v1/profile` | Yes | Get student profile |
| POST | `/api/v1/profile` | Yes | Create student profile |
| PATCH | `/api/v1/profile` | Yes | Update student profile |
| POST | `/api/v1/generate` | Yes | Start textbook generation |
| GET | `/api/v1/status/{id}` | Yes | Poll generation status |
| GET | `/api/v1/textbook/{path}` | Yes | Fetch rendered HTML |

---

## Frontend Routes

| Path | Purpose | Auth Required |
|------|---------|---------------|
| `/` | Redirect to `/dashboard` or `/login` | No |
| `/login` | Google Sign-In | No |
| `/onboarding` | Profile creation form | Yes |
| `/dashboard` | Profile summary + generation form | Yes |
| `/textbook/[id]` | Textbook viewer | Yes |

---

## How to Verify

```bash
# Backend tests (all 76 should pass)
cd backend && uv run pytest tests/ -v

# Lint (should be clean)
cd backend && uv run ruff check src/ tests/

# Start backend server
cd backend && uv run uvicorn textbook_agent.interface.api.app:app --reload

# Start frontend
cd frontend && npm run dev

# Test auth manually (requires GOOGLE_CLIENT_ID in .env):
# 1. Open http://localhost:5173
# 2. Should redirect to /login
# 3. Sign in with Google
# 4. Should redirect to /onboarding (first time) or /dashboard
# 5. Complete profile → redirects to dashboard
# 6. Generate a textbook from the dashboard
```

---

## What Is NOT Done (Phase 4 Candidates)

1. **Quality loop re-run** — `QualityChecker` generates a report but does not re-run failed nodes.
2. **PDF output** — Only HTML rendering is implemented.
3. **Real LLM integration tests** — All tests use `MockProvider`.
4. **Frontend styling polish** — Functional dark theme but no design system for components.
5. **Persistent job storage** — Jobs are still in-memory (`app.state.jobs`). The `generations` DB table exists but is not yet wired to the generation flow.
6. **Error recovery** — No retry at the API level if a generation fails.
7. **Token refresh** — JWT has a 7-day expiry but no refresh token flow.
8. **Profile editing** — The PATCH endpoint exists but the frontend always redirects to full onboarding form.
9. **Past generations list** — The dashboard does not yet show previous generations.
10. **Production CORS/security** — CORS restricted to frontend origin but no rate limiting, CSRF, or CSP headers.

---

## For the Next Agent

If you are picking up this project:

1. **Run `cd backend && uv run pytest`** to verify all 76 tests pass.
2. **Read `CLAUDE.md`** at project root for project conventions.
3. **Set `GOOGLE_CLIENT_ID`** in both `backend/.env` and `frontend/.env` (`VITE_GOOGLE_CLIENT_ID`) to test auth end-to-end.
4. **The architecture guard** still enforces DDD layer boundaries.
5. **StudentProfile → LearnerProfile hydration** happens in `GenerateTextbookUseCase._build_learner_profile()`.
6. **All API endpoints except `/health` and `/auth/google` require a valid JWT** via the `get_current_user` dependency.
7. **The database is auto-created** on first startup via the lifespan handler in `app.py`.
8. **MockProvider** in `conftest.py` is unchanged from Phase 2. Tests override `get_current_user` and `get_student_profile_repository` via FastAPI dependency overrides.

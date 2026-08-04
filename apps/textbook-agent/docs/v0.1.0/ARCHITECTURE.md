# Architecture - v0.1.0

## Overview

The Textbook Generation Agent is a full-stack application with a Python/FastAPI backend and SvelteKit frontend. The backend uses Domain-Driven Design (DDD) with four layers. The core domain is a 6-node pipeline that transforms a learner profile into a personalized textbook. Users authenticate via Google OAuth and maintain a persistent student profile that personalises all generated content.

## System Diagram

```
┌─────────────────────────────────┐     ┌─────────────────────┐
│       SvelteKit Frontend        │────▶│   FastAPI Backend    │
│  (Login, Dashboard, Onboarding, │◀────│   (REST API)        │
│   Generation, Viewer)           │     └────────┬────────────┘
└─────────────────────────────────┘              │
                                        ┌────────▼────────────┐
                                        │  Application Layer   │
                                        │  (Use Cases, Agent)  │
                                        └────────┬────────────┘
                                                  │
                                        ┌────────▼────────────┐
                                        │   Domain Layer       │
                                        │  (Pipeline Nodes,    │
                                        │   Schemas, Prompts)  │
                                        └────────▲────────────┘
                                                  │ implements ports
                                        ┌────────┴────────────┐
                                        │ Infrastructure Layer │
                                        │ (LLM Providers,     │
                                        │  Auth, DB, Renderer) │
                                        └─────────────────────┘
```

## DDD Layer Architecture

### Interface Layer (`interface/`)

**Purpose**: Delivery mechanisms. Receives external input and delegates to the application layer.

- `api/routes/` - FastAPI routes: health, auth, profile, generation
- `api/middleware/` - Authentication middleware (JWT validation)
- `api/app.py` - App factory, CORS, lifespan (DB init)
- `api/dependencies.py` - Dependency injection container

**Depends on**: Application layer only.

### Application Layer (`application/`)

**Purpose**: Orchestration and use case coordination. Translates between interface and domain.

- `use_cases/` - `GenerateTextbookUseCase`, `CheckQualityUseCase`
- `orchestrator.py` - `TextbookAgent` wires the 6-node pipeline
- `dtos/` - Request/response objects for layer boundaries

**Depends on**: Domain layer (entities, ports).

### Domain Layer (`domain/`)

**Purpose**: Core business logic. Zero framework dependencies (only `pydantic` for schema validation).

- `entities/` - `GenerationContext`, `StudentProfile`, `User`, `CurriculumPlan`, `SectionContent`, etc.
- `value_objects/` - `Depth`, `NotationLanguage`, `EducationLevel`, `LearningStyle`, `SectionDepth`
- `services/` - The 6 pipeline nodes that ARE the business logic
- `prompts/` - Pedagogical rules and prompt construction (domain knowledge)
- `ports/` - Abstract interfaces (`BaseProvider`, `TextbookRepository`, `UserRepository`, `StudentProfileRepository`)
- `exceptions.py` - Domain-specific errors

**Depends on**: Nothing external. This is the innermost layer.

### Infrastructure Layer (`infrastructure/`)

**Purpose**: Adapters for external systems. Implements domain ports.

- `providers/` - `AnthropicProvider`, `OpenAIProvider`, `ProviderFactory`
- `auth/` - Google OAuth token verification, JWT handler
- `database/` - SQLAlchemy models, async session factory (SQLite)
- `repositories/` - `FileTextbookRepository`, `SqlUserRepository`, `SqlStudentProfileRepository`
- `storage/` - `FileSystemStorage` (reads profiles, writes outputs)
- `renderer/` - `HTMLRenderer` (pure Python, no LLM) + CSS design system
- `config/` - `Settings` (Pydantic Settings from `.env`)

**Depends on**: Domain ports (implements them).

## Dependency Rule

```
Interface → Application → Domain ← Infrastructure
```

Domain NEVER imports from any other layer. Infrastructure implements domain ports via dependency inversion.

## Authentication Flow

1. User clicks "Sign in with Google" in the frontend
2. Frontend receives Google ID token via Google Identity Services
3. Frontend sends token to `POST /api/v1/auth/google`
4. Backend verifies token with Google, creates or updates user in SQLite
5. Backend issues a JWT and returns it with user info
6. Frontend stores JWT in localStorage, attaches to all API calls
7. All generation/profile endpoints require valid JWT via `get_current_user` dependency

## Student Profile & Personalisation

The `StudentProfile` entity captures persistent learner context:
- Age, education level, learning style, interests, goals, prior knowledge
- Preferred notation and depth defaults
- `learner_description` - free-text manual override describing abilities, gaps, and signals (will be populated by automated diagnostics in a future phase)

On generation, `StudentProfile` is merged with the per-request `GenerationRequest` (subject + context) into a `GenerationContext`. This ephemeral context carries everything the pipeline needs to personalise content — it is built fresh each time and never stored. The `prior_knowledge` and `learner_description` fields from the student profile are injected into planner and content prompts to personalise examples, vocabulary, and analogies.

## The 6-Node Pipeline

```
GenerationContext (hydrated from StudentProfile + request)
     ↓
[Node 1] CurriculumPlanner    → CurriculumPlan
     ↓
[Node 2] ContentGenerator     → list[SectionContent]     (per section)
     ↓
[Node 3] DiagramGenerator     → list[SectionDiagram]     (per section needing visual)
     ↓
[Node 4] CodeGenerator        → list[SectionCode]        (per section needing code)
     ↓
[Node 5] Assembler            → RawTextbook               (pure Python, no LLM)
     ↓
[Node 6] QualityChecker       → QualityReport             (LLM validates)
     ↓
  PASS → HTMLRenderer → final output
  FAIL → re-run flagged nodes → check again
```

Every node inherits from `PipelineNode[TInput, TOutput]` with:
- Typed input/output schemas enforced by Pydantic
- Retry logic (default 2 retries)
- Validation before and after execution

## Provider Architecture

All LLM calls go through the abstract `BaseProvider` port:

```python
class BaseProvider(ABC):
    def complete(self, system_prompt, user_prompt, response_schema, ...) -> Any: ...
    def name(self) -> str: ...
```

Swapping Claude for GPT-4 is a config change. The domain never knows which provider is active.

## Database

SQLite via SQLAlchemy (async). Three tables:
- `users` - Google-authenticated user accounts
- `student_profiles` - Persistent learner profiles (1:1 with users)
- `generations` - Textbook generation jobs

Tables are auto-created on app startup via `Base.metadata.create_all`.

## Frontend

SvelteKit with TypeScript. Key routes:
- `/login` - Google Sign-In
- `/onboarding` - Student profile creation (after first login)
- `/dashboard` - Profile summary + generation form
- `/textbook/[id]` - Rendered textbook viewer

Core components:
- `ProfileSetup` - Onboarding form (education level, interests, learning style, age, goals)
- `ProfileForm` - Generation request form (subject + context only)
- `GenerationProgress` - Real-time pipeline status
- `TextbookViewer` - Renders the HTML textbook output

Auth state managed via `$lib/stores/auth.ts`. JWT attached to all API calls via `apiFetch()`.

Communicates with backend via REST API (`/api/v1/auth/*`, `/api/v1/profile`, `/api/v1/generate`, `/api/v1/status/{id}`).

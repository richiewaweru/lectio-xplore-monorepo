# Development Workflow - v0.1.0

## Development Environment

### Backend

```bash
cd backend

# Install all dependencies including dev tools
uv sync --all-extras

# Run tests
uv run pytest -v

# Run tests with coverage
uv run pytest --cov=textbook_agent

# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/

# Start dev server
uv run uvicorn textbook_agent.interface.api.app:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev

# Type check
npx svelte-check --tsconfig ./tsconfig.json

# Build
npm run build
```

## Testing

### Backend Test Structure

```
tests/
├── conftest.py              # Shared fixtures (GenerationContext loaders, MockProvider)
├── fixtures/                # Learner profile JSON files
│   ├── stem_beginner.json
│   ├── stem_intermediate.json
│   └── stem_advanced.json
├── domain/
│   ├── test_entities.py     # Schema validation (GenerationContext, CurriculumPlan, etc.)
│   ├── test_prompts.py      # Prompt builder output validation
│   ├── test_nodes.py        # Pipeline node execution with MockProvider
│   └── test_student_profile.py  # StudentProfile, User, enum validation
├── application/
│   └── test_orchestrator.py # Full pipeline with MockProvider
├── infrastructure/
│   ├── test_providers.py    # Provider factory tests
│   ├── test_renderer.py     # HTML rendering output
│   └── test_auth.py         # JWT handler round-trip
└── interface/
    └── test_api.py          # FastAPI endpoint tests (health, auth, generation)
```

### Running Tests

```bash
cd backend

# All tests (76 should pass)
uv run pytest

# Specific test file
uv run pytest tests/domain/test_entities.py

# Specific test class
uv run pytest tests/domain/test_entities.py::TestGenerationContext

# Verbose output
uv run pytest -v
```

### Test Fixtures

Three learner profiles are provided as test fixtures:

| Fixture | Subject | Age | Depth | Language |
|---|---|---|---|---|
| `stem_beginner.json` | algebra | 14 | survey | plain |
| `stem_intermediate.json` | calculus | 17 | standard | math_notation |
| `stem_advanced.json` | linear algebra | 22 | deep | math_notation |

All three must produce valid output through the full pipeline.

### Test Dependencies

- **MockProvider** (`conftest.py`) returns canned Pydantic instances keyed by `response_schema` type. To test a new node, add a canned response to `_MOCK_RESPONSES`.
- **Auth overrides** (`test_api.py`) use FastAPI's `dependency_overrides` to mock `get_current_user` and `get_student_profile_repository`, avoiding real DB/Google auth in tests.

## Code Style

- **Python**: Enforced by `ruff` (line length: 100)
- **TypeScript/Svelte**: Default SvelteKit formatting

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | No | Health check |
| POST | `/api/v1/auth/google` | No | Exchange Google ID token for JWT |
| GET | `/api/v1/auth/me` | Yes | Get current authenticated user |
| GET | `/api/v1/profile` | Yes | Get student profile |
| POST | `/api/v1/profile` | Yes | Create student profile |
| PATCH | `/api/v1/profile` | Yes | Update student profile |
| POST | `/api/v1/generate` | Yes | Start textbook generation (returns 202) |
| GET | `/api/v1/status/{id}` | Yes | Poll generation status |
| GET | `/api/v1/textbook/{path}` | Yes | Fetch rendered HTML |

## DDD Layer Rules

When adding code, respect the dependency direction:

1. **Domain** (`domain/`) - Never import from application, infrastructure, or interface
2. **Application** (`application/`) - May import from domain only
3. **Infrastructure** (`infrastructure/`) - May import from domain (implements ports)
4. **Interface** (`interface/`) - May import from application and domain

If you find yourself importing from a wrong direction, introduce a port (abstract interface) in the domain layer.

## Key Entity Relationships

```
StudentProfile (persistent, DB)          GenerationRequest (per-request DTO)
         \                                        /
          \______ merged by use case _____________/
                         |
                         v
               GenerationContext (ephemeral)
                         |
                         v
                  6-Node Pipeline
                         |
                         v
                    RawTextbook → HTMLRenderer → HTML output
```

- `StudentProfile` stores who the student is (age, education, interests, goals, learner_description)
- `GenerationRequest` carries what to generate now (subject, context, optional depth/language overrides)
- `GenerationContext` is assembled fresh for each run and is what the pipeline nodes consume

## Adding a New Pipeline Node

1. Define input/output schemas in `domain/entities/`
2. Create the node class in `domain/services/` inheriting `PipelineNode[TInput, TOutput]`
3. Add prompt builder in `domain/prompts/`
4. Wire into the orchestrator in `application/orchestrator.py`
5. Add tests in `tests/domain/`

## Adding a New Field to StudentProfile

1. Add the field to `domain/entities/student_profile.py`
2. Add the column to `infrastructure/database/models.py` (`StudentProfileModel`)
3. Map it in `infrastructure/repositories/sql_student_profile_repo.py` (create, update, _to_entity)
4. Add it to `interface/api/routes/profile.py` (`ProfileCreateRequest` and `ProfileUpdateRequest`)
5. If it should flow into generation, add it to `domain/entities/generation_context.py`
6. If it should flow into generation, map it in `application/use_cases/generate_textbook.py` (`_build_generation_context`)
7. If it should appear in prompts, update `domain/prompts/planner_prompts.py` (`_learner_block`)
8. Update frontend types in `frontend/src/lib/types/index.ts`
9. Update frontend form in `frontend/src/lib/components/ProfileSetup.svelte`

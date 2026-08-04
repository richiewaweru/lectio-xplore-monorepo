# Phase 3.1 Handoff — LearnerProfile → GenerationContext Rename + learner_description

**Date:** 2026-03-11
**Base:** Phase 3 complete (76 tests, 0 lint errors)
**Status:** COMPLETE — rename done across all layers, new fields wired, 76 tests passing, 0 lint errors

---

## What Was Done

This phase eliminated the naming confusion between `StudentProfile` (persistent) and `LearnerProfile` (ephemeral) by renaming the latter to `GenerationContext`. It also added two new personalisation signals — `prior_knowledge` (already on StudentProfile but not mapped through) and `learner_description` (brand new free-text field) — and wired them end-to-end from the database to the LLM prompts.

### Core Changes

| # | Change | Files Affected |
|---|--------|----------------|
| 1 | Renamed `LearnerProfile` → `GenerationContext` | ~22 files across all layers |
| 2 | Deleted `domain/entities/learner_profile.py` | — |
| 3 | Created `domain/entities/generation_context.py` | New file with all original fields + `prior_knowledge` + `learner_description` |
| 4 | Added `learner_description` to `StudentProfile` | `domain/entities/student_profile.py` |
| 5 | Added `learner_description` column to DB | `infrastructure/database/models.py` |
| 6 | Mapped `learner_description` in SQL repo | `infrastructure/repositories/sql_student_profile_repo.py` (create, update, _to_entity) |
| 7 | Added `learner_description` to API | `interface/api/routes/profile.py` (create + update request schemas) |
| 8 | Wired `prior_knowledge` + `learner_description` into use case | `application/use_cases/generate_textbook.py` (`_build_generation_context`) |
| 9 | Injected both fields into LLM prompts | `domain/prompts/planner_prompts.py`, `domain/prompts/content_prompts.py` |
| 10 | Frontend: added `learner_description` to types | `frontend/src/lib/types/index.ts` |
| 11 | Frontend: added textarea to onboarding form | `frontend/src/lib/components/ProfileSetup.svelte` |
| 12 | Frontend: displays field on dashboard | `frontend/src/routes/dashboard/+page.svelte` |
| 13 | Updated test references | `tests/conftest.py`, `tests/domain/test_entities.py` |
| 14 | Updated docs | `ARCHITECTURE.md`, `SCHEMAS.md` |

---

## Detailed File Changes

### Domain Layer

| File | Change |
|------|--------|
| `domain/entities/learner_profile.py` | **Deleted** |
| `domain/entities/generation_context.py` | **Created** — same fields as old `LearnerProfile` plus `prior_knowledge: str` and `learner_description: str` |
| `domain/entities/__init__.py` | Export `GenerationContext` instead of `LearnerProfile` |
| `domain/entities/student_profile.py` | Added `learner_description: str = ""` field |
| `domain/entities/textbook.py` | `profile: LearnerProfile` → `profile: GenerationContext` |
| `domain/services/planner.py` | All `LearnerProfile` refs → `GenerationContext` |
| `domain/services/content_generator.py` | `profile: LearnerProfile` → `profile: GenerationContext` |
| `domain/services/assembler.py` | `profile: LearnerProfile` → `profile: GenerationContext` |
| `domain/prompts/planner_prompts.py` | Import rename + `_learner_block` now emits `prior_knowledge` and `learner_description` lines |
| `domain/prompts/content_prompts.py` | Import rename, type annotations updated |
| `domain/ports/file_storage.py` | `read_profile` returns `GenerationContext` |

### Application Layer

| File | Change |
|------|--------|
| `application/orchestrator.py` | `generate(profile: LearnerProfile)` → `generate(profile: GenerationContext)`, docstring updated |
| `application/use_cases/generate_textbook.py` | `_build_learner_profile` → `_build_generation_context`, now maps `prior_knowledge` and `learner_description` from `StudentProfile` |

### Infrastructure Layer

| File | Change |
|------|--------|
| `infrastructure/storage/file_storage.py` | `LearnerProfile` → `GenerationContext` |
| `infrastructure/database/models.py` | Added `learner_description = Column(Text, default="")` to `StudentProfileModel` |
| `infrastructure/repositories/sql_student_profile_repo.py` | Maps `learner_description` in `create()`, `update()`, and `_to_entity()` |

### Interface Layer

| File | Change |
|------|--------|
| `interface/api/routes/profile.py` | `ProfileCreateRequest` and `ProfileUpdateRequest` include `learner_description` |

### Frontend

| File | Change |
|------|--------|
| `src/lib/types/index.ts` | `StudentProfile` and `ProfileCreateRequest` include `learner_description` |
| `src/lib/components/ProfileSetup.svelte` | New `learnerDescription` state + textarea in Background section |
| `src/routes/dashboard/+page.svelte` | Conditionally displays `learner_description` in profile summary |

### Tests

| File | Change |
|------|--------|
| `tests/conftest.py` | `LearnerProfile` → `GenerationContext` (imports + fixture type hints) |
| `tests/domain/test_entities.py` | `TestLearnerProfile` → `TestGenerationContext`, all `LearnerProfile()` → `GenerationContext()` |

### Docs

| File | Change |
|------|--------|
| `docs/v0.1.0/ARCHITECTURE.md` | Entity list, Student Profile section, pipeline diagram — all updated to `GenerationContext` |
| `docs/v0.1.0/SCHEMAS.md` | `LearnerProfile` section → `GenerationContext` with full expanded field table and example |

---

## Architecture Decision: Two-Entity Model

The project now has a clear two-entity model for learner data:

```
StudentProfile (persistent, stored in DB)
    ├─ age, education_level, learning_style, interests, goals
    ├─ prior_knowledge
    ├─ learner_description  ← NEW: manual diagnostic signal
    └─ preferred_notation, preferred_depth

            ┆ merged by use case per generation
            ▼

GenerationContext (ephemeral, never stored)
    ├─ all StudentProfile fields above
    ├─ subject, context  ← from GenerationRequest
    └─ depth, language   ← overrides or defaults from profile
```

`StudentProfile` is **who the student is** — persistent across sessions, updated via profile PATCH.

`GenerationContext` is **what to generate now** — built fresh by `_build_generation_context()` in the use case, consumed by the pipeline, then discarded.

The `learner_description` field exists on both: stored persistently on `StudentProfile`, and carried through into `GenerationContext` for prompt injection. In a future phase, this field will be populated by automated diagnostic assessments rather than manual input.

---

## Prompt Injection

The `_learner_block()` helper in `planner_prompts.py` (shared by content prompts) now emits:

```
LEARNER:
- Age: 17
- Education level: high_school
- Depth requested: standard
- Learning style: visual
- Context: I understand derivatives but integration confuses me
- Interests: physics, gaming
- Goals: Prepare for AP Calculus exam
- Prior knowledge: Comfortable with algebra and trigonometry
- Learner description: Strong at mechanical procedures but struggles with conceptual understanding
```

The last two lines are new. Both are conditional — omitted when empty.

---

## Test Results

```
76 passed in 14.43s
ruff: All checks passed!
```

No test changes to logic — only import/class renames. All 76 tests continue to pass.

---

## Database Migration Note

The `learner_description` column was added to the `StudentProfileModel`. Since we use `Base.metadata.create_all()` on startup:

- **New databases**: Column is created automatically.
- **Existing databases**: The column will NOT be added automatically by `create_all()` (SQLAlchemy limitation). You must either:
  - Delete the existing `textbook_agent.db` file (acceptable for dev), or
  - Run `ALTER TABLE student_profiles ADD COLUMN learner_description TEXT DEFAULT '';`

---

## How to Verify

```bash
# All 76 tests should pass
cd backend && uv run pytest tests/ -v

# Lint should be clean
cd backend && uv run ruff check src/ tests/

# Verify no remaining references to old name
rg "LearnerProfile|learner_profile" backend/src/ backend/tests/
# Expected: no matches

# Verify GenerationContext is used throughout
rg "GenerationContext" backend/src/ --count
# Expected: matches in ~12 files
```

---

## For the Next Agent

1. **`LearnerProfile` no longer exists.** The class is now `GenerationContext` in `domain/entities/generation_context.py`.
2. **`StudentProfile` → `GenerationContext` hydration** happens in `GenerateTextbookUseCase._build_generation_context()`.
3. **`learner_description`** is a free-text field on both `StudentProfile` and `GenerationContext`. It flows: frontend form → API → DB → use case → prompt. Currently manual; future phase will automate via diagnostic signals.
4. **`prior_knowledge`** was already on `StudentProfile` but is now properly mapped through `GenerationContext` into the prompts.
5. **Test fixture JSON files** (`tests/fixtures/stem_*.json`) did not need changes — the new fields have defaults.
6. **Existing databases need migration** — see note above.

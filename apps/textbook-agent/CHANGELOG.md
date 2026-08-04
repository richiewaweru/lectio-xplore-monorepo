# Changelog

All notable changes to this project will be documented in this file.

The format follows Keep a Changelog conventions with SemVer release tags.

## [1.0.0-beta.1] - 2026-08-01

### Features
- Added the destination-first Units workspace with versioned paths, explicit approval, recoverable structural edits, and durable lesson preparation.
- Added teaching schedules, learner groups, controlled lesson shapes, deterministic resource projections, and unit-scoped Results.
- Added append-only lesson actuals and aggregate diagnostic marks with advisory misconception summaries.
- Added read-only compatibility wrappers that expose existing packs as one-lesson legacy units without migrating or rewriting data.
- Added server-controlled global and account-scoped V2 capability flags, persistent mutation audit events, and limits on expensive planning and composition routes.

### Bug Fixes
- Preserved path-owned objectives, canonical concept identity, provenance, and approved structure across preparation, regeneration, projections, and outcomes.
- Corrected starting-knowledge prerequisite projection and excluded stale non-V3 compatibility generations from V2 wrappers.
- Normalized advisory planner output variations and downgraded non-blocking review recommendations so usable production lessons are not reported as failed.
- Kept Legacy Studio, Builder, Lectio rendering, pack printing, and PDF paths available alongside the V2 beta.
- Updated vulnerable frontend and backend dependencies to patched releases and replaced `python-jose` with PyJWT to remove its vulnerable ECDSA dependency.

### Breaking Changes
- None for existing Legacy Studio or pack data. Xplore V2 is additive and can be hidden with `XPLORE_V2_ENABLED=false`.

### Other
- Added reversible migrations through `20260801_0028` and a production rollback procedure that disables V2 without deleting its data.
- Deferred the 30-lesson comparative human study until after the complete beta is deployed; the user owns that broader tuning review after the one-lesson release smoke passes.

## [0.1.0] - 2026-03-11

### Added
- Phase 1: Full project scaffolding — DDD backend (FastAPI), SvelteKit frontend, all entity schemas, pipeline node base class, 3 test fixtures, provider factory, HTML renderer skeleton.
- Phase 2: Runtime logic — all 6 pipeline nodes implemented, both LLM providers (Anthropic + OpenAI), HTML renderer with dark-theme CSS, orchestrator with progress callbacks, async generation API, frontend wiring. 64 tests.
- Phase 3: Authentication & profiles — Google OAuth + JWT, persistent student profiles (SQLite), profile CRUD API, onboarding flow, dashboard, CLI removed. 76 tests.
- Phase 3.1: Renamed `LearnerProfile` to `GenerationContext` for clarity. Added `learner_description` free-text field and wired `prior_knowledge` through prompts.

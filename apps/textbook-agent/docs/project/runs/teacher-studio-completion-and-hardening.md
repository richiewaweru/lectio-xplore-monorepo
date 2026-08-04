# Teacher Studio Completion And Hardening

**Extends**: `docs/project/runs/teacher-studio-program.md`
**Status**: implemented, hardened, merged to `main`
**Merged PRs**: `#11`, `#12`, `#13`

## Feature: Teacher Studio completion and repo cleanup

**Classification**: major
**Subsystems**: backend, frontend, docs, repo

### Progress
- [x] Understood requirements and identified scope
- [x] Read relevant source code and project rules
- [x] Refreshed Textbook contracts from the sibling Lectio repo
- [x] Completed the planning-layer architecture cleanup
- [x] Finished the `/studio` planning, review, and generation experience
- [x] Cut the dashboard over to `/studio`
- [x] Added tests for new planning and studio behavior
- [x] Ran validation and architecture checks
- [x] Landed the rollout, hardening, and repo-hygiene follow-ups on `main`
- [x] Recorded handoff and operational notes

## What Changed

### 1. Teacher Studio rollout completed

The canonical teacher creation flow now lives at `/studio` and covers the full `idle -> planning -> reviewing -> generating` sequence.

- The frontend studio shell, planning stream, review surface, and generation workspace were finished
- The dashboard no longer embeds the legacy studio and now routes teachers into `/studio`
- Generation remains inside the studio until completion instead of bouncing directly to the standalone textbook view

### 2. Planning layer aligned to the agreed architecture

The planning package was completed as a shell-owned layer and hardened against boundary leaks and contract drift.

- Textbook contracts were refreshed from the sibling `C:\Projects\lectio` repo so the harmonized Lectio catalog is now the source of truth
- Planning no longer depends on pipeline enums in `prompt_builder.py`
- Deterministic fallback, template scoring, budget enforcement, and role handling were strengthened
- `/api/v1/brief/commit` remains the single approval and generation-start boundary
- Legacy `POST /api/v1/brief` now emits deprecation signaling

### 3. Additional hardening landed after the main rollout

After the main completion pass, a follow-up audit landed targeted fixes in PR `#12`.

- Fixed planning-model validation and template validation gaps
- Hardened generation bridge fallback behavior
- Tightened SSE event handling and progress completion behavior
- Added planning and interface tests for the audited gaps

### 4. Repo hygiene was cleaned up

The repo is now clean on `main` without trying to commit local runtime artifacts.

- Root-level `backend.zip`, `frontend.zip`, `structure.txt`, and `textbook_agent.db` are now ignored
- Local and remote non-`main` branches were cleaned up so the repo currently operates with a single canonical branch

## Key Files And Areas

### Backend
- `backend/src/planning/`
- `backend/src/pipeline/contracts.py`
- `backend/src/textbook_agent/interface/api/routes/brief.py`
- `backend/src/textbook_agent/interface/api/routes/generation.py`
- `backend/tests/planning/test_planning.py`
- `backend/tests/interface/test_brief.py`

### Frontend
- `frontend/src/lib/components/studio/TeacherStudioFlow.svelte`
- `frontend/src/lib/components/studio/IntentForm.svelte`
- `frontend/src/lib/components/studio/PlanStream.svelte`
- `frontend/src/lib/components/studio/PlanReview.svelte`
- `frontend/src/lib/components/studio/GenerationView.svelte`
- `frontend/src/routes/dashboard/+page.svelte`

### Docs
- `docs/project/ARCHITECTURE.md`
- `docs/project/SCHEMAS.md`
- `docs/project/agent-context.md`
- `CLAUDE.md`

## Decisions

- **Decision**: Treat `/studio` as the canonical teacher flow.
  **Reason**: The new plan-review-commit flow is now fully implemented and tested.
  **Alternatives considered**: Leaving the dashboard-embedded studio as primary would have kept two teacher entry paths alive longer than needed.

- **Decision**: Keep `POST /api/v1/brief/commit` as the single approval boundary.
  **Reason**: This preserves an explicit teacher approval moment while ensuring the exact approved spec is what gets generated.
  **Alternatives considered**: Splitting approval and generation into separate public endpoints would add more state transitions and more room for drift.

- **Decision**: Ignore root workspace artifacts instead of committing them.
  **Reason**: The zip files, filesystem listing, and local SQLite DB are machine-local state, not portable source artifacts.
  **Alternatives considered**: Committing them would bloat the repo and leak local runtime data.

## Validation

### Textbook repo
- `python tools/agent/validate_repo.py --scope all`
- `python tools/agent/check_architecture.py --format text`

### Lectio repo
- `npm run export-contracts`
- `npm run check`
- `npm run test`

### Runtime verification
- Backend `GET /docs` returned `200` after restart on `2026-03-28`
- Frontend `GET /` returned `200` after restart on `2026-03-28`

## Validation Results

- `python tools/agent/validate_repo.py --scope all`: pass
- `python tools/agent/check_architecture.py --format text`: pass, no architecture violations found
- `C:\Projects\lectio -> npm run export-contracts`: pass
- `C:\Projects\lectio -> npm run check`: pass
- `C:\Projects\lectio -> npm run test`: pass
- Backend health check on `http://127.0.0.1:8000/docs`: pass
- Frontend health check on `http://127.0.0.1:5173/`: pass

## Publish Record

- PR `#11`: completed the Teacher Studio rollout
- PR `#12`: hardened planning and integration after deep audit
- PR `#13`: ignored local workspace artifacts so `main` stays clean

## Risks And Follow-up

- No required follow-up remains for the Teacher Studio completion plan itself
- A stale folder may remain at `.claude/worktrees/distracted-haibt` if Windows keeps a handle on it; it is no longer a registered git worktree or branch
- Local runtime data and environment files remain machine-local and intentionally untracked

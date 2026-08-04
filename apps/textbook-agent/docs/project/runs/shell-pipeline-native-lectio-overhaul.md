## Refactor: Shell + Pipeline + Native Lectio

**Classification**: major
**Scope**: backend generation shell, pipeline engine, persistence, frontend generation/viewer flow
**Behavior changes**:
- Pipeline becomes the only live generation engine
- Canonical artifact becomes structured JSON document, not HTML
- Frontend switches from polling + iframe HTML to SSE + native Lectio rendering

### Progress
- [x] Documented scope and interfaces affected
- [x] Mapped current dependencies
- [ ] Established baseline (all tests passing before changes)
- [x] Implemented structural change
- [x] Verified all existing tests still pass (behavior preserved where intended)
- [x] Added tests for new interfaces
- [x] Ran full validation (backend + frontend)
- [x] Updated documentation if architecture rules changed
- [x] Self-reviewed against agents/standards/architecture.md

### Validation Evidence
- `python tools/agent/check_architecture.py --format text` -> passed with no architecture violations
- `uv sync --all-extras` -> completed and installed required backend tooling
- `uv run pytest` in `backend/` -> `56 passed`
- `npm test` in `frontend/` -> `8 files passed, 26 tests passed`
- `npm run check` in `frontend/` -> passed with `0 errors, 0 warnings`
- `npm run build` in `frontend/` -> passed
- `python tools/agent/validate_repo.py --scope all` -> passed end to end

### Risks and Follow-up
- Baseline validation was not captured before the overhaul work on this branch, so the evidence above reflects the final integrated state rather than a before/after test comparison.
- Frontend production deployment still needs a concrete SvelteKit adapter instead of `adapter-auto`.
- Frontend build emits non-failing chunk-size and circular chunk warnings that should be monitored if the app grows further.

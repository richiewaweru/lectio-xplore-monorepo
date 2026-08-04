## Feature: login flow and auth routing fix

**Classification**: major
**Subsystems**: frontend, backend

### Progress
- [x] Understood requirements and identified scope
- [x] Read relevant source code and project rules
- [x] Implemented the change
- [x] Wrote tests for new behavior
- [x] Ran validation (backend: ruff + pytest, frontend: check + test)
- [x] Self-reviewed against agents/standards/review.md
- [ ] Wrote commit message(s) following agents/standards/communication.md
- [ ] Updated PR description with summary, validation evidence, risks
- [x] Noted any follow-up work or open questions

### Validation Evidence
- `cd frontend && npm run check` -> `svelte-check found 0 errors and 0 warnings`
- `cd frontend && npm run test` -> `5 passed`
- `cd frontend && npm run build` -> success
- `cd backend && uv run ruff check src tests` -> `All checks passed!`
- `cd backend && uv run pytest tests/interface/test_api.py` -> `14 passed`
- `cd backend && uv run pytest` -> `110 passed, 6 deselected`
- `python tools/agent/check_architecture.py --format text` -> `No architecture violations found.`

### Risks and Follow-up
- The Google OAuth client configuration remains an external dependency. This change only fixes frontend session bootstrapping and routing behavior.
- App startup will now depend on `/api/v1/auth/me` for session validation; stale local storage tokens should no longer control routing.
- Non-401 failures during `/api/v1/auth/me` bootstrap currently preserve the locally stored session to avoid logging users out during transient backend failures. If stricter server-authoritative behavior is preferred, that can be tightened in a follow-up.

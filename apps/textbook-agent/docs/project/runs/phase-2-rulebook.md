## Feature: phase 2 rulebook implementation

**Classification**: major
**Subsystems**: backend, frontend

### Progress
- [x] Understood requirements and identified scope
- [x] Read relevant source code and project rules
- [x] Implemented the change
- [x] Wrote tests for new behavior
- [x] Ran validation (backend: ruff + pytest, frontend: check + build)
- [x] Self-reviewed against agents/standards/review.md
- [ ] Wrote commit message(s) following agents/standards/communication.md
- [ ] Updated PR description with summary, validation evidence, risks
- [x] Noted any follow-up work or open questions

### Phase Checklist
- [x] Baseline validation captured
- [x] Rulebook schemas implemented
- [x] Rulebook CSS implemented
- [x] Prompt bundle and traceability implemented
- [x] Mechanical quality checks implemented
- [x] Renderer template updated for the rulebook layout
- [x] Frontend viewer switched to authenticated iframe rendering
- [x] Provider/runtime hardening completed
- [x] End-to-end and integration coverage expanded
- [ ] Manual browser verification completed for Claude
- [ ] Manual browser verification completed for OpenAI

### Validation Evidence
- Baseline backend tests: `cd backend && uv run pytest` -> `88 passed, 2 deselected`
- Baseline backend lint: `cd backend && uv run ruff check src/ tests/` -> clean
- Baseline frontend checks: `cd frontend && npm run check` -> `0 errors, 0 warnings`
- Schema update backend tests: `cd backend && uv run pytest` -> `90 passed, 2 deselected`
- Schema update backend lint: `cd backend && uv run ruff check src/ tests/` -> clean
- Prompt bundle tests: `cd backend && uv run pytest tests/domain/test_prompts.py tests/domain/test_nodes.py tests/application/test_orchestrator.py` -> `32 passed`
- Prompt bundle lint: `cd backend && uv run ruff check src/ tests/` -> clean
- Mechanical quality tests: `cd backend && uv run pytest tests/domain/test_quality_rules.py tests/domain/test_nodes.py tests/application/test_orchestrator.py` -> `20 passed`
- Mechanical quality lint: `cd backend && uv run ruff check src/ tests/` -> clean
- Renderer and API regression tests: `cd backend && uv run pytest tests/infrastructure/test_renderer.py tests/application/test_orchestrator.py tests/interface/test_api.py` -> `21 passed`
- Renderer/frontend lint and checks: `cd backend && uv run ruff check src/ tests/` -> clean; `cd frontend && npm run check` -> `0 errors, 0 warnings`
- Runtime hardening integration smoke tests: `cd backend && uv run pytest tests/integration/test_real_pipeline.py -m integration -rs -vv` -> `6 passed in 408.76s`
- Final backend suite: `cd backend && uv run pytest` -> `100 passed, 6 deselected`
- Final backend lint: `cd backend && uv run ruff check src/ tests/` -> clean
- Final frontend checks: `cd frontend && npm run check` -> `0 errors, 0 warnings`
- Final frontend build: `cd frontend && npm run build` -> success
- Manual standalone HTML artifacts generated from real providers:
  - `backend/outputs/manual_rulebook_smoke/anthropic.html`
  - `backend/outputs/manual_rulebook_smoke/openai.html`

### Risks and Follow-up
- The rulebook PDF itself is not machine-extracted in-repo; implementation follows the user's supplied Claude summary plus repo constraints.
- Manual browser verification in the running app is still pending for both providers; only automated checks and standalone HTML artifact generation were completed in this phase.
- API keys appear to be present in local example environment files; rotation should happen after this phase, but credential cleanup was kept out of scope here per the implementation brief.

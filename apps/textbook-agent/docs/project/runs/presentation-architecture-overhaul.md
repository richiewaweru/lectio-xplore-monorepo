## Refactor: presentation architecture overhaul

**Classification**: major
**Scope**: backend presentation contracts, semantic adapter, renderer engine, template configs, presentation QA, metadata persistence
**Behavior changes**: textbook HTML shifts from the single rulebook theme to the new template-driven presentation engine while keeping the generation/viewer API stable

### Progress
- [x] Documented scope and interfaces affected
- [x] Mapped current dependencies
- [x] Established baseline (all tests passing before changes)
- [x] Implemented structural change
- [x] Verified all existing tests still pass (behavior preserved where intended)
- [x] Added tests for new interfaces
- [x] Ran full validation (backend + frontend)
- [x] Updated documentation if architecture rules changed
- [x] Self-reviewed against agents/standards/architecture.md

### Validation Evidence
- `python tools/agent/check_architecture.py --format text` -> `No architecture violations found.`
- `cd backend && uv run pytest tests/infrastructure/test_renderer.py tests/application/test_orchestrator.py tests/interface/test_api.py tests/integration/test_mock_pipeline_render.py` -> `31 passed`
- `cd backend && uv run pytest tests/infrastructure/test_renderer.py tests/infrastructure/test_presentation_engine.py tests/application/test_orchestrator.py tests/interface/test_api.py tests/integration/test_mock_pipeline_render.py` -> `36 passed`
- `python tools/agent/validate_repo.py --scope all` -> backend ruff pass, backend pytest `120 passed`, frontend check pass, tooling pytest `7 passed`

### Milestone 1 Scope
- Internal-first rollout only
- Adapter-first migration from `SectionContent`
- Stable generation endpoints, viewer contract, and single HTML artifact
- Implement T01 Concept Explorer, T02 Notebook Calm, and T10 Minimal Print
- Persist presentation metadata with rendered textbooks

### Risks and Follow-up
- Presentation QA can identify content-shape problems before prompt guidance exists; those issues will be classified explicitly even when the renderer can only fall back, not self-heal content.
- Template gallery, teacher selection, and later template families remain follow-on work after the internal engine stabilizes.
- Manual artifact review for algebra, calculus, and chemistry print previews is still a recommended follow-up outside automated validation.

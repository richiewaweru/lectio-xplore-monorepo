## Bugfix: Diagram series generation + repair path

**Classification**: minor
**Root cause**: Three stacked issues: diagram-series frame compilation emits one frame only, visual repair target parsing conflates section and visual IDs, and deterministic missing-component checks route visual components to section-writer repair.

### Progress
- [x] Reproduced the bug (or identified the failing code path)
- [x] Identified root cause
- [x] Implemented the fix
- [x] Added regression test
- [ ] Ran validation
- [x] Self-reviewed the diff

### Validation Evidence
- Attempted: `uv run pytest backend/tests/v3_execution/test_compile_orders_series_frames.py backend/tests/v3_review/test_v3_review_targets.py backend/tests/v3_review/test_v3_review_deterministic.py -q`
- Result: failed before test execution due to uv cache access denial.
- Attempted: `$env:UV_CACHE_DIR='C:\Projects\Textbook agent\.uv-cache'; uv run python -m pytest tests/v3_execution/test_compile_orders_series_frames.py tests/v3_review/test_v3_review_targets.py tests/v3_review/test_v3_review_deterministic.py -q` (workdir `backend/`)
- Result: failed before test execution due to environment import error: `ImportError: DLL load failed while importing _pydantic_core: Access is denied.`

### Risks
- Validation is currently blocked by local Python environment/DLL permissions; runtime correctness is not yet empirically confirmed by tests in this session.
- `_extract_series_frames` relies on marker patterns (`Panel|Step|Frame N`) and intentionally falls back to a single frame when markers are absent.

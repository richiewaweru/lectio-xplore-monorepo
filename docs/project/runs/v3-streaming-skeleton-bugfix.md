# Bugfix: V3 streaming skeleton and schema metadata

**Classification**: major
**Root cause**: V3 section assembly stores internal ordering metadata in section buckets, then validates the same buckets against a generated Lectio Pydantic model with `extra='forbid'`. Separately, generation only persists the document at draft/final pack time, so `/document` stays empty until after wave1 completes and the frontend has no canvas section stubs for live component events.

### Progress
- [x] Reproduced the bug (or identified the failing code path)
- [x] Identified root cause
- [x] Implemented the fix
- [x] Added regression test
- [x] Ran validation
- [x] Self-reviewed the diff

### Validation Evidence
- Phase 1: `cd backend && $env:LECTIO_CONTRACTS_DIR='C:\Projects\Textbook agent\backend\contracts'; uv run pytest tests/v3_execution/test_booklet_status.py tests/v3_execution/test_section_builder_tolerant.py -q` -> 17 passed, 1 warning.
- Phase 2: `cd backend && $env:LECTIO_CONTRACTS_DIR='C:\Projects\Textbook agent\backend\contracts'; uv run pytest tests/v3_execution/ tests/generation/ -q` -> 138 passed, 1 warning.
- Phase 3: `cd frontend && npm run test -- v3-print-canvas v3-stream-state v3` -> 14 test files passed, 61 tests passed.
- Phase 3 typecheck: `cd frontend && npm run check` -> svelte-check found 0 errors and 0 warnings.
- Final architecture: `python tools/agent/check_architecture.py --format text` -> No architecture violations found.
- Full validation attempt: `python tools/agent/validate_repo.py --scope all` timed out after 5 minutes without a final result.
- Backend lint: `cd backend && uv run ruff check src/ tests/` found 2 unrelated existing issues outside this change (`src/media/diagnostics/v3_image_pipeline_diagnostic.py` unused `asyncio`; `tests/v3_execution/test_compile_orders_series_frames.py` unused `vis`). Left untouched because media image pipeline edits are out of scope.
- Touched backend lint: `cd backend && uv run ruff check <changed backend files>` -> All checks passed.
- Tooling tests: `cd backend && uv run python -m pytest ..\tools\agent\tests` -> 8 passed.
- Frontend build: `cd frontend && npm run build` -> built successfully, with existing large chunk warnings.

### Risks
- Skeleton persistence must not weaken export gates or change the empty-document 404 behavior.
- Frontend skeleton painting must not clobber a canvas that already has streamed content.

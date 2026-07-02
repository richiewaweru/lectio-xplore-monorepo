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

### Risks
- Skeleton persistence must not weaken export gates or change the empty-document 404 behavior.
- Frontend skeleton painting must not clobber a canvas that already has streamed content.

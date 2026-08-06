# Gate 1 — Native-only routing

## Pass

Native generations no longer enter legacy `retry_failed_section` / stage2 back-half paths.

## Changes

- Added `planning/whole_lesson/native_routing.py` with `generation_is_native_whole_lesson(state, generation=None)`.
- Native if any of: `context.native_whole_lesson`, `page_document_v2`, top-level `native_whole_lesson`, `document_contract_version >= 2`, or status/stage in `NATIVE_STATUSES`.
- `post_chunked_retry_section`: native → requeue `failed_recoverable → queued`, else HTTP 409 `NativeRetryRequired` (never calls `retry_failed_section`).
- Legacy stage2 pipeline still records `LegacyBackHalfDisabled` without invoking `resume_stage2`.

## Tests

`tests/planning/test_native_only_routing.py`

- native detector coverage
- spy proves legacy retry not called
- failed_recoverable requeue path
- legacy stage2 source gate remains blocked

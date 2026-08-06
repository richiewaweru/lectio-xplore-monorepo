# Gate 8 — Native status projection

## Pass

Chunked status exposes native progress fields; polling stops on native terminals.

## Changes

- `V3ChunkedStatusDTO` extended with document/section/block counters, `failed_*_ids`, and `error_detail`.
- `project_native_status` reads `page_document_v2` (not legacy stage2 fields).
- Next-action map: approve_teaching / wait / retry_native / inspect_error / done / wait_visuals / none.
- Failed terminals always project a non-null `error` message plus structured `error_detail`.
- Frontend `v3.ts` adds `writing_sections` and optional native fields.
- Studio poller stops on `failed_recoverable`, `failed_terminal`, `ready`, and keeps polling on `writing_sections`.

## Tests

`tests/planning/test_native_status_payload.py`

# Gate 4 — Immediate validation and informed repair

## Pass

Writer content is validated before ready persistence; one informed repair attempt runs inside `dispatch_writer_async`.

## Summary

- `ContentValidationError` carries structured path/message errors.
- Scripted provider supports invalid→valid and permanent-invalid scenarios.
- Repair prompt includes prior output + validation errors (not a blind re-call).
- Executor treats post-writer `ContentValidationError` as `VALIDATION` with `retryable=True`, `repairable=False` (no second blind repair).

## Tests

- `tests/generation/test_writer_repair.py`
- `tests/planning/test_phase02_failure_classification.py` (`test_content_validation_error_not_executor_repairable`)

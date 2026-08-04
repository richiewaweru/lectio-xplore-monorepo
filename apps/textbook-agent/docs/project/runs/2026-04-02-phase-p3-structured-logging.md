# Phase P3 Structured Logging

**Date:** 2026-04-02  
**Classification:** major  
**Subsystems:** backend logging, startup/runtime configuration, request middleware, pipeline observability

## Progress

- [x] Confirmed the current repo state and established a validation baseline
- [x] Moved shared logging setup into `core/`
- [x] Added canonical `JSON_LOGS` and `LOG_LEVEL` settings with compatibility alias support
- [x] Rewired app startup logging and request-id middleware
- [x] Added generation and node context adapters
- [x] Updated env examples for the new logging contract
- [x] Ran final validation
- [x] Recorded manual logging smoke checks

## Summary

This phase makes backend logs queryable in production without changing API behavior. Structured JSON logging is now controlled by `JSON_LOGS`, request logs carry `request_id`, generation job logs carry `generation_id` and `user_id`, and the existing pipeline node warning/info logs now carry `generation_id`, `section_id`, and `node_name`.

## Notes

- This pass builds on the landed P1 and P2 changes and does not revert them.
- `JSON_LOGS` is now the preferred runtime env name; `JSON_LOGGING` remains accepted as a compatibility alias during this phase.
- The implementation stays on the standard library `logging` module and does not introduce `structlog` or similar tooling.

## Validation Evidence

- `uv run pytest` in `backend/` passed: `222 passed`
- `python tools/agent/check_architecture.py --format text` passed: no architecture violations found
- `python tools/agent/validate_repo.py --scope all` passed:
  - backend Ruff
  - backend pytest
  - frontend `npm run check`
  - frontend `npm run build`
  - tooling pytest

## Manual Logging Smoke Checks

- Readable local output:
  - `uv run python -c "import logging; from core.logging import configure_logging; configure_logging(json_logs=False, level=logging.INFO); logging.getLogger('demo').info('readable-log-check')"`
  - result: human-readable line `06:30:28 INFO     demo readable-log-check`
- JSON generation log:
  - `uv run python -c "import logging; from core.logging import configure_logging; from generation.logging import GenerationLogger; configure_logging(json_logs=True, level=logging.INFO); GenerationLogger('gen-smoke','user-smoke').info('json generation log')"`
  - result: single-line JSON including `generation_id` and `user_id`
- JSON node log:
  - `uv run python -c "import logging; from core.logging import configure_logging; from core.llm.logging import NodeLogger; configure_logging(json_logs=True, level=logging.INFO); NodeLogger(generation_id='gen-smoke', section_id='section-smoke', node_name='diagram_generator').warning('json node log')"`
  - result: single-line JSON including `generation_id`, `section_id`, and `node_name`
- SQL logger split:
  - `uv run python -c "import logging; from core.logging import configure_logging; configure_logging(json_logs=False, level=logging.DEBUG); print('LOCAL_SQL_LEVEL', logging.getLogger('sqlalchemy.engine').level); configure_logging(json_logs=True, level=logging.DEBUG); print('JSON_SQL_LEVEL', logging.getLogger('sqlalchemy.engine').level)"`
  - result: `LOCAL_SQL_LEVEL 10` and `JSON_SQL_LEVEL 30`, confirming DEBUG locally and WARNING in JSON mode

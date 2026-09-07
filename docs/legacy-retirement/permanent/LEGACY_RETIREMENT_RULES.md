# Legacy Retirement Rules

Classify every legacy subsystem:
- MIGRATE_AND_DELETE
- DELETE_NOW
- KEEP_CANONICAL
- DATA_RETIREMENT_REQUIRED
- UNKNOWN_BLOCKER

Trace:
imports, routes, frontend consumers, workers/startup, DB, telemetry, config/env, package exports, tests, scripts/CI, docs.

If not part of Unit→Print or Unit→Learn:
migrate live consumers → remove legacy-only dependencies/tests/docs/config → handle DB safely → delete subsystem.

Do not keep legacy merely because a legacy test references it.
Do not delete migration history.

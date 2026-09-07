# Regression Policy

A phase cannot PASS merely because imports compile.

Minimum regression coverage after every structural phase:

- relevant backend unit/integration tests
- `@lectio/page` tests/check
- `@lectio/learn` tests/build
- Builder tests
- domain-boundary tests
- frontend type/check/test subset affected by moves
- Alembic import/metadata sanity if DB models move
- one Page golden fixture where the phase touches Print
- one Component/Learn golden fixture where the phase touches Learn

No migrations should be generated solely because Python model files moved.

If behavior output changes, the phase is not a pure refactor and must be stopped/reported.

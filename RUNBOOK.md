# Xplore Learning Platform V2 Runbook

Run from `C:\Projects\Textbook agent` in PowerShell unless a command changes directory.

## Phase 0 baseline

Baseline source commit:

```powershell
git rev-parse xplore
```

Backend test suite:

```powershell
Set-Location backend
uv run pytest -q
Set-Location ..
```

Architecture gate:

```powershell
python tools/agent/check_architecture.py --format text
```

Frontend production build:

```powershell
Set-Location frontend
npm run build
Set-Location ..
```

Baseline fixture integrity:

```powershell
Get-FileHash backend/tests/fixtures/xplore_v2_phase0_generation.json -Algorithm SHA256
```

## Working protocol

At the start of every session:

1. Read `PROGRESS.md` completely.
2. Confirm the current phase and verified evidence.
3. Re-run that phase's gate before relying on prior work.
4. Update `PROGRESS.md` before ending the session, including partial work.

Before every commit, re-check the nine invariants from the controlling goal and run
the phase-specific tests, relevant lint, and architecture gate. Commit one logical
change at a time with a `P{n}:` prefix in the commit subject.

## Production beta release and rollback

Release version: `1.0.0-beta.1`. Deploy backend and frontend from the same commit.

Required backend settings:

```text
APP_ENV=production
RUN_MIGRATIONS_ON_STARTUP=true
XPLORE_V2_ENABLED=true
XPLORE_V2_BETA_USERS=<comma-separated beta user IDs or emails, or empty for all authenticated users>
```

Pre-deploy checklist:

1. Confirm `git status --short` is empty and the release commit is on `xplore`.
2. Run `uv run pytest -q` and `uv run ruff check src tests` in `backend`.
3. Run `pnpm exec vitest run`, `pnpm run check`, and `pnpm run build` in `frontend`.
4. Run `python tools/agent/check_architecture.py --format text` at repository root.
5. Run `uv run python tools/validate_v2_audit_migration.py` in `backend`.
6. Run `uv run --with pip-audit pip-audit` in `backend`, then `pnpm audit --audit-level high` and
   `npm audit --audit-level=high` in `frontend`; all three must report no known vulnerabilities.
7. Confirm the Phase 0 fixture SHA256 remains
   `91E0BCB220BF9E2532B13AEF9FE7447AD822AB109D9D226DC032D5ADB4540FD2`.

Production smoke checklist:

1. `GET /health` is healthy and reports `1.0.0-beta.1`.
2. An authorized beta account receives `xplore_v2=true` from `GET /api/v1/capabilities`, sees
   Units, and can still open Home and Legacy.
3. A non-eligible account receives `xplore_v2=false`; `/api/v1/units` is `404`, while
   `/api/v1/packs` and Legacy Studio remain usable.
4. Existing packs appear under Compatibility and open through their original pack route.
5. Create a unit, plan/approve its path, prepare one lesson, and confirm the durable review link
   survives reload. Confirm queue progress never reports partial completion as success.
6. Open the prepared lesson in Builder, render it through Lectio, and export one PDF. Confirm images
   load and the response has a non-zero page count and file size.
7. Save one reversible unit edit and verify a matching `v2_audit_events` row with request ID,
   actor, path, status, and timestamp.
8. Review error rate, `429` volume, generation queue depth/age, failed/partial generations, PDF
   failures, and audit persistence before widening the allowlist.

Exposure rollback (preferred):

1. Set `XPLORE_V2_ENABLED=false` in the backend environment and restart/redeploy the backend.
2. Verify `GET /api/v1/capabilities` returns `false`, Units disappears, `/units` redirects to Lessons,
   and direct V2 API calls return `404`.
3. Verify Legacy Studio, packs, Builder, Lectio rendering, and PDF export remain healthy.
4. Leave migrations and V2 rows in place. Re-enable with the same release after correction.

Migration recovery:

- Migration `20260801_0028` is additive and creates only `v2_audit_events` plus its indexes.
- If deployment fails before application traffic, roll the schema back one revision with Alembic,
  correct the release, and rerun the upgrade.
- If V2 traffic has occurred, prefer the exposure rollback above. Export or retain audit rows before
  any schema downgrade; never use a migration downgrade as the normal product kill switch.

Support triage:

- Capture account ID/email, UTC timestamp, request ID, route, unit/path/lesson IDs, and the visible
  error state. Do not request learner-identifying response data; marks are aggregate-only.
- A `404` on every V2 route with healthy legacy routes usually means capability rollout or the kill
  switch. A `409` usually means stale revision or an unmet approval/preparation guard. A `429` means
  the caller exceeded an expensive-action limit.
- For generation incidents, distinguish failed, partial, awaiting-review, and complete states before
  retrying. Retry only the affected lesson/variant/resource when the workflow exposes that action.
- Correlate mutation incidents through `v2_audit_events.request_id` and structured application logs.

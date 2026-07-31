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

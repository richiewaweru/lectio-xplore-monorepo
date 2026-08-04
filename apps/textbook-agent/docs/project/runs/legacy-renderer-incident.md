## Bugfix: legacy renderer failure on canonical port 8000

**Classification**: major
**Root cause**: a stale backend runtime on port `8000` continued serving the pre-presentation-refactor renderer, which still loaded the deleted `assets/base.css` file. The frontend also lacked a single shared API-target resolver and the backend did not persist failure classification or expose runtime fingerprints, so the incident looked like a current code regression instead of a legacy runtime failure.

### Progress
- [x] Reproduced the failing code path from persisted generation records and runtime logs
- [x] Identified root cause
- [x] Implemented the fix
- [x] Added regression tests
- [x] Ran validation
- [x] Self-reviewed the diff

### Validation Evidence
- `cd backend && uv run pytest tests/infrastructure/test_generation_repo.py tests/interface/test_runtime_diagnostics.py tests/interface/test_api.py tests/infrastructure/test_renderer.py tests/infrastructure/test_presentation_engine.py tests/application/test_orchestrator.py -q`
- `cd frontend && npm run test -- src/lib/api/config.test.ts src/lib/api/client.test.ts src/lib/generation/error-messages.test.ts src/lib/generation/failure-labels.test.ts`
- `cd frontend && npm run check`
- `python tools/agent/check_architecture.py --format text`

### Risks
- Historical generation timestamps still reflect mixed pre-fix storage semantics. They are preserved, but should not be used for precise incident duration analysis.
- If another non-standard listener reclaims `8000`, the health fingerprint and startup smoke check will make the mismatch visible sooner, but the host-level cleanup still has to succeed operationally.

### Incident Facts
- The DB contained `8` failed draft generations between `2026-03-13 21:42` and `23:12` with the missing `base.css` path.
- The current renderer path no longer reads `assets/base.css`; the old committed renderer did.
- A clean draft generation completed successfully on the current presentation renderer while the stale runtime failures were still being persisted.

### Runtime Verification
- Check backend identity: `Invoke-WebRequest http://127.0.0.1:8000/health`
- Check frontend-served client target: `Invoke-WebRequest http://127.0.0.1:5173/src/lib/api/client.ts`
- Verify the served client bundle and `/health` both reference the same runtime before starting new generations.

### Timestamp Note
- New generation timestamps are normalized to UTC-aware datetimes at the entity boundary.
- Historical rows are intentionally preserved as-is; the fix does not rewrite old timestamps.

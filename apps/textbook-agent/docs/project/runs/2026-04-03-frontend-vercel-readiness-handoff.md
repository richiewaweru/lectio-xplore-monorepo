# Frontend Vercel Readiness Handoff

## Feature: frontend vercel readiness patch

**Classification**: minor  
**Subsystems**: frontend

### Progress
- [x] Understood requirements and identified scope
- [x] Read relevant source code and project rules
- [x] Implemented the change
- [x] Wrote tests for new behavior
- [x] Ran validation (backend: n/a, frontend: check + test + build)
- [x] Self-reviewed against agents/standards/review.md
- [x] Wrote commit message(s) following agents/standards/communication.md
- [x] Updated handoff with summary, validation evidence, risks
- [x] Noted follow-up work or open questions

### Summary
- Added `frontend/vercel.json` with a non-API rewrite to `/index.html` for deep-link SPA fallback on Vercel.
- Updated frontend env resolution to accept `PUBLIC_GOOGLE_CLIENT_ID` with fallback to `VITE_GOOGLE_CLIENT_ID`.
- Refreshed login and env tests to cover the expanded Google client ID contract.
- Fixed the stale `lectio` test mock in `LectioDocumentView.test.ts` so the full frontend suite passes again.
- Updated the frontend README to match the actual npm-based Vercel deployment path and current vendored Lectio setup.

### Validation Evidence
- `cd frontend && npm run check` -> passed
- `cd frontend && npm run test` -> passed (`25` files, `77` tests)
- `cd frontend && npm run build` -> passed

### Risks and Follow-up
- Manual Vercel smoke testing is still outstanding after deploy: direct deep-link refresh, Google login popup/origin check, and backend-backed streaming.
- The external deployment note in `C:\Users\richi\Downloads\DEPLOY-FRONTEND.md` was refreshed locally for operator use, but it is not part of the repository commit.

### Where To Start
- Env compatibility logic: `frontend/src/lib/config/environment.ts`
- Deep-link hosting fallback: `frontend/vercel.json`
- User-facing deployment notes: `frontend/README.md`

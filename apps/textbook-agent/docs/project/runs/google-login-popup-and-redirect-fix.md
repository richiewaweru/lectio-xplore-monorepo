## Bugfix: Google login popup and post-login redirect

**Classification**: minor
**Root cause**: The login page only attempted navigation inside the credential callback, so successful auth could still leave the user stranded on `/login`. The Google Identity widget was also mounted without explicit prompt/popup configuration, which made the UX less consistent than needed.

### Progress
- [x] Reproduced the bug (or identified the failing code path)
- [x] Identified root cause
- [x] Implemented the fix
- [x] Added regression test
- [x] Ran validation
- [x] Self-reviewed the diff

### Validation Evidence
- `cd frontend && npm run check` -> `svelte-check found 0 errors and 0 warnings`
- `cd frontend && npm run test` -> `6 passed`
- `cd frontend && npm run build` -> success
- Added regression coverage in `frontend/src/lib/auth/google.test.ts` and `frontend/src/lib/auth/routing.test.ts`

### Risks
- Browser and Google-managed sign-in surfaces are still not fully app-controlled. The fix can prefer prompt/popup style flows, but the exact visual treatment remains browser and Google dependent.
- Production browser behavior still depends on Google Identity Services and browser support for FedCM / One Tap surfaces. This change improves preference and redirect reliability, but it cannot force an embedded first-party modal owned by the app.

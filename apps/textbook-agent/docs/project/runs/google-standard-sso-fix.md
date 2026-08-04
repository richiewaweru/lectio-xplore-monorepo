## Bugfix: standard Google SSO button flow

**Classification**: minor
**Root cause**: The login page drifted away from the standard Google Identity Services button flow by adding extra browser-managed prompt configuration and helper behavior. That made the click path less reliable than the normal documented `initialize + renderButton + callback` implementation.

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
- Frontend dev server restarted and `/login` returns `200` on `http://127.0.0.1:5173/login`

### Risks
- The Google sign-in surface is still Google-controlled, so final UX details depend on browser and Google behavior. This fix only restores the standard supported button flow in the app.

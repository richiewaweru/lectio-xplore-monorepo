# Runtime topology evidence — 2026-09-18

## Requested topology

- Docker service: repository PostgreSQL container `textbook-agent-db-1` only.
- Local backend: `uvicorn` on `127.0.0.1:8001`.
- Local frontend: Vite on `127.0.0.1:5173`.
- Browser: Codex In-app Browser with authenticated teacher session.

## Verification

- The repository DB container was healthy and exposed localhost port 5432.
- The local backend health endpoint returned HTTP 200 with the native Lectio
  pipeline architecture.
- The local frontend served the live UI at port 5173.
- Migrations were applied through `20260913_0042` after database ownership was
  repaired for the configured application role.
- The unrelated old Compose database container was stopped but not deleted; it
  contained no campaign lesson IDs.
- The app was restarted and Google authentication completed in the retained
  In-app Browser tab. Authenticated calls to `/api/v1/auth/google`,
  `/api/v1/auth/me`, and `/api/v1/units` returned HTTP 200.

## Browser/runtime notes

- The browser retained the teacher session through the live preparation,
  approval, Learn/Print, publishing, assignment, learner join, interaction,
  refresh, and completion checks recorded in the case files.
- Process-scoped PDF and Playwright timeouts were used for the live server;
  repository environment files and credentials were not changed.
- Browser download completion was observed in the UI, but the in-app browser
  did not expose the resulting PDF files for filesystem visual inspection.

## Redaction

Passwords, tokens, email addresses, provider keys, and private profile fields
are intentionally omitted.

# Xplore V2 Production Beta Handoff

Release: `v1.0.0-beta.1` (`20a0231`)

## Delivered

The full unit/path product is implemented alongside the existing lesson and pack workflows. A
teacher can define a destination, plan and approve a recoverable path, organize periods and groups,
prepare controlled lesson variants, compose deterministic resources, and record aggregate outcomes.
Existing packs appear as computed one-lesson compatibility entries and remain in their original
tables and routes.

Operational controls include global and account-scoped V2 capability flags, persistent mutation
auditing, request IDs, expensive-route rate limits, reversible migrations, and a no-data-loss kill
switch. The frontend fails closed when capability lookup fails and redirects a disabled V2 account
from `/units` to the existing `/lessons` workspace.

## Automated evidence

- Backend: 512 tests passed; one pre-existing Pydantic field-shadow warning.
- Planning/compatibility slice: 54 tests passed.
- Frontend: 76 files and 307 tests passed.
- Svelte diagnostics: 0 errors and 0 warnings.
- Production frontend bundle: passed.
- Frontend pnpm and npm audits: no known vulnerabilities.
- Backend pip audit: no known vulnerabilities; the local project package is skipped because it is
  not a PyPI distribution.
- Ruff: passed.
- Architecture guard: no violations.
- Migration `0028`: upgrade, downgrade, and second upgrade passed.
- Phase 0 fixture SHA256 remains `91E0BCB220BF9E2532B13AEF9FE7447AD822AB109D9D226DC032D5ADB4540FD2`.

Local authenticated browser acceptance passed capability on/off, compatibility ownership, unit
workflow, Lectio rendering, a two-page PDF export, persistent audit evidence, and rollback behavior.
Production-infrastructure evidence is recorded in `PROGRESS.md`.

## Production smoke evidence

- Railway service `text-book-generator Copy` and Vercel project `text-book-generator-s1l3`
  activated the same `xplore` release commit. V3 deployments were left untouched.
- Production generation `8e3d6391-f11d-4d5d-8db3-6f2ef221ade2` completed preparation, concept
  review, approval, and a four-section lesson in Builder.
- Builder lesson `9c0bcaab-d18a-4e30-9d6f-18acb9811488` exported a 258,079-byte Teacher PDF.
  Its five pages were rendered and visually checked with no clipping, overlap, broken glyphs, or
  unreadable tables.
- Output-shape recommendations no longer fail a usable production lesson. Harmless omitted fields,
  display-text length variation, missing exact prior-knowledge phrasing, and incomplete optional
  components on an otherwise renderable section are normalized or shown as minor recommendations.
  Objective ownership, canonical concept identity, prerequisites, approved slots/order, component
  contracts, shared checks, access control, and unusable output remain strict failures.

## Known limitations and next work

- Classes and global Results are not shown as empty navigation destinations. Results remain
  available where real unit/lesson data exists.
- V2 remains beta and Legacy remains available during evaluation.
- The user owns the deferred 30-lesson study after deployment. It may change
  versioned prompts, skeletons, classifier behavior, toggles, and defaults; it must not weaken
  objective ownership, prerequisite, provenance, revision, or access-control guards.

## Deployment and rollback

Apply migrations through `20260801_0028`, configure the capability environment variables, deploy
the backend and frontend from the same release commit, and follow the production smoke checklist in
`RUNBOOK.md`. To roll back product exposure, set `XPLORE_V2_ENABLED=false` and redeploy/restart the
backend. Do not downgrade or delete V2 tables for an exposure rollback.

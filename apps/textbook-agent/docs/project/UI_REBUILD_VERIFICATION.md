# Lectio UI Rebuild — Verification Report

Date: 2026-09-14

## Summary

Frontend product shell and Lesson Workspace (Plan / Learn / Print) are in place. Teachers navigate Units → Unit → Lesson without Studio/Builder as primary concepts. Publish → Assign no longer requires pasting a LearnRelease UUID. Public `/join` and titled student home are wired with thin backend glue.

## Automated checks

| Check | Result |
| --- | --- |
| `units/[id]/page.test.ts` (18) | PASS |
| `shared/auth/routing.test.ts` (8) | PASS |
| `tests/routes/test_learn_runtime.py` (incl. join) | PASS |

## Product surfaces delivered

- **AppShell** sidebar: Home, Classes, Resources, Insights, Settings
- **Units / Unit Workspace**: Evidence tab (was Results), Learning Groups label, Open Lesson / Prepare Lesson
- **Lesson Workspace** `/units/:id/lessons/:lessonId/{plan,learn,print}`
- **Plan**: prepare → structural → teaching → approve → Create Learn / Create Print
- **Learn**: DocumentEditor palette + interaction editors + Publish + Assign dialog
- **Print**: Preview / Edit / Issues / Download PDF dialog
- **Classes** at `/classes` (redirect from `/learn/classes`); no UUID assign field
- **Join** at `/join` → session token → student home with lesson titles
- **Settings** grouped Teaching Profile / AI Instructions / Account

## Backend glue

- `POST /api/v1/learn/classes/join` (public)
- `get_optional_user` for learner home / instance reads with `X-Learner-Session`
- Learner home instances include `title` from assignment/release

## Mandatory Chromium flows

| Flow | Status | Notes |
| --- | --- | --- |
| Teacher Learn E2E | PENDING live | Requires running app + auth; structure and API wiring are in place |
| Teacher Print E2E | PENDING live | Print workspace loads `/document` + editor + PDF export client |
| Student round-trip | PENDING live | `/join` + titled home ready; needs live class invite |

Run Live Chromium against a seeded unit before release. Record route transitions, console errors, and network failures.

## Known remaining issues

1. Compatibility routes `/studio*` and `/builder*` still exist (intentional shims).
2. Plan workspace polls chunked status; long generations still use V3 APIs under the product shell.
3. Interaction editors patch safe config fields only — no new grading semantics.
4. Insights landing links into class Insights tab; detailed insight page remains at `/learn/classes/:id/insight`.
5. Full Chromium E2E not executed in this automated pass (no live server session in CI agent).

## Final quality questions (teacher)

1. Where am I? — breadcrumbs + sidebar
2. What lesson? — Lesson Workspace header
3. Ready? — status badge Not prepared / Preparing / Ready / Needs attention
4. Make Learn? — Plan approved → Create Learn / Learn tab
5. Make Print? — Create Print / Print tab
6. Assign? — Publish → Assign to class (no UUID)
7. Evidence? — Unit Evidence tab + Classes Insights

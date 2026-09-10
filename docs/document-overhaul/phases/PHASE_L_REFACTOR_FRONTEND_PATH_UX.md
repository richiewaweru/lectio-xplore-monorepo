# Phase L — Refactor Frontend Path UX

## Goal
Make the UI reflect one shared planning flow followed by an explicit independent Print or Learn production choice.

## Open these active files first
- `apps/textbook-agent/frontend/src/routes/units/`
- `apps/textbook-agent/frontend/src/routes/studio/`
- `apps/textbook-agent/frontend/src/routes/builder/`
- `apps/textbook-agent/frontend/src/routes/learn/`
- `apps/textbook-agent/frontend/src/lib/curriculum/`
- `apps/textbook-agent/frontend/src/lib/print/`
- `apps/textbook-agent/frontend/src/lib/learn/`
- `apps/textbook-agent/frontend/src/lib/api/`

## Implementation tasks
- Keep shared Unit/Teaching Plan review UI before path selection.
- Make path generation explicit: Generate Print or Generate Learn.
- Do not present 'convert Learn to Print' or 'convert Print to Learn'.
- After one path exists, allow returning to the Teaching Plan and generating the sibling path.
- Remove legacy component insertion menus and template/component assumptions from Learn authoring.
- Keep the existing dashboard/application shell unless a specific dependency on deleted architecture requires change.

## Expected outputs
- `updated path-choice UI`
- `updated Unit realization status/open links`
- `new Learn document insertion controls`
- `frontend routing tests`

## Acceptance gate
From the UI, a teacher can approve one Teaching Plan, generate only Learn, return, generate only Print, and open each independent result.

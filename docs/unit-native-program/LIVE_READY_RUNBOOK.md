# Live-ready runbook — Unit Print/Learn (post-P08)

Prepared for P09 live campaign. **No test-only adapters** are required on user
routes: closed Print production and closed Learn production use production
services from an approved shared teaching revision.

## Prerequisites

- P08 PASS (see `docs/unit-native-program/reports/P08_PHASE_REPORT.md`)
- Real provider credentials configured for the application (not pytest mocks)
- Dedicated test teacher + learner identities; disposable/test DB
- App build green: `pnpm app:check` and frontend build
- Browser available for UI inspection; Poppler/`pdftoppm` recommended for PDF page images
- Follow `docs/unit-native-program/pack/verification/LIVE_PROTOCOL.md`

## Verified production commands (deterministic / local)

Recorded in `COMMAND_MAP.md`. From repo root unless noted:

| Purpose | Command |
| --- | --- |
| Frontend typecheck | `pnpm app:check` |
| Frontend build | `pnpm --dir apps/textbook-agent/frontend build` |
| Domain guards | `pnpm program:domain-guards` |
| `@lectio/page` | `pnpm page:test` / `pnpm page:check` |
| `@lectio/learn` | `pnpm --dir packages/lectio-learn test` / `check` |
| P08 integration suite | `cd apps/textbook-agent/backend && uv run pytest -q tests/print_learn/test_p08_integration_gates.py` |

## User routes (no test adapters)

1. **Unit prepare** — product Unit UI / `POST .../lessons/{id}:prepare`
2. **Shared teaching** — plan + approve via studio teaching review
   (`run_and_persist_teaching_plan` → `approve_teaching_and_queue`)
3. **Print** — post-approval worker uses `build_closed_print_production_plan`
   (`form_prompt=closed_print_selection`); open `/studio/print/{generation_id}`;
   export student/teacher PDF via product export route
4. **Learn** — `produce_learn_from_approved_teaching` /
   `build_closed_learn_production` (`form_prompt=closed_learn_selection`);
   open Builder on the editable lesson; preview; publish release; assign; learner runtime
5. **Realizations** — `POST .../realizations` for both paths on the same teaching
   revision; `POST .../realizations/{id}:retry` isolates one path

## Live campaign cases

Use LIVE_PROTOCOL cases A–D. For each case record a filled
`pack/tracking/LIVE_RUN_TEMPLATE.json` under
`docs/unit-native-program/evidence/live/` (never under `evidence/mocks/`).

## Mock policy

Deterministic P08 evidence under `evidence/mocks/p08/` labels mocks in
`i06-mock-catalogue.json`. **Do not** treat those runs as live PASS.

## Controlled failure (live)

Use existing safe failure injection at writer boundary on one designated run;
resume via normal retry UI/API; confirm sibling path unchanged.

## Unblock notes

- P05-P04 page images still need Poppler on PATH
- Live providers/browser must be available before claiming P09 gates

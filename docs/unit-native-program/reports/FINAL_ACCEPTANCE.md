# Final acceptance — Unit Print/Learn implementation pack

Repository: `richiewaweru/lectio-xplore-monorepo` (local `C:\Projects\lectio`)  
Branch: `feat/unit-print-learn`  
Pack-reviewed base: `5d1563903a22d6d40e12a86dcc4d9021ca8202a3`  
Implementation tip at P09 write-up: see `git log` / STATE `implementation_head`.

## Core dual-path acceptance

**Result: NOT COMPLETE (PASS_WITH_BLOCKERS)**

Achieved on live case A with real providers:

- Unit constructor/path/prepare through product API
- Shared teaching planned and approved (live LLM)
- Print closed selection + writers to `ready` on the same teaching revision
- Learn closed production + realization from that revision (`form_prompt=closed_learn_selection`)
- Publish release v1 for `native_learn` + start learner instance

Still blocking full core acceptance:

- Only one of four LIVE_PROTOCOL cases completed
- Product PDF export timed out (Playwright → frontend print route)
- Poppler/`pdftoppm` missing for page-image inspection
- Learner attempt persistence not demonstrated on case A (teaching plan had no Sequence-required action; content-only Learn surfaces)
- Controlled failure recovery + release v2 not completed live
- Google Sign-In browser path not automated

## Full-catalogue acceptance

**Result: NOT COMPLETE**

| Capability | Status |
|---|---|
| Sequence | generation-ready; deterministic writer; used in P06–P08 proofs |
| Choice / multi-select / fill-blank / numeric / short-response / match-pairs / classify | package shells exist; writers largely not generation-ready |
| ImageHotspot / DragLabel | unavailable (denied) |
| Print forms (prose, list, table, figure, questions, choices, …) | closed selection + writers on Unit path (live Print ready observed) |

## Phase / gate totals

| Phase | Status |
|---|---|
| P00–P08 | PASS (see prior reports) |
| P09 | PASS_WITH_BLOCKERS |

Live evidence: `docs/unit-native-program/evidence/live/` (never under `evidence/mocks/`).

## Migrations

- `20260908_0041_add_native_realizations` applied on local Postgres `textbook_agent`.

## How to resume live B–D

1. Backend + frontend up; Poppler on PATH optional for images.
2. `cd apps/textbook-agent/backend && uv run python scripts/run_p09_live_campaign.py --cases B,C,D`
3. For PDF: confirm `http://127.0.0.1:5173/studio/print/{id}?print=true` loads with valid token before claiming V02.
4. Prefer teaching plans that emit `sequence` + `order-items` (or learner_action) when proving attempt persistence.

## Reproduce

See `docs/unit-native-program/LIVE_READY_RUNBOOK.md` and `COMMAND_MAP.md`.

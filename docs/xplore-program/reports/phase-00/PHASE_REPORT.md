# PHASE 00 REPORT — Baseline + Reuse Inventory + Guardrails

Status: PASS

## Baseline at start
- repo: C:\Projects\lectio (lectio-xplore-monorepo)
- branch: main
- starting SHA: bd19a9060b637b84f6d86c002cbf01513adf1e4b
- dirty state: untracked evidence/logs/images only (tracked clean)
- previous phase report read: none (Phase 00)
- source lineages recorded:
  - Textbook agent xplore @ d2cf2f27c1841591b804b115fc3dfe9b0fb23c9a (dirty)
  - lectio-legacy-20260805 xplore @ f71e78cdbb06a2169c60b937213fa4db6996c69f (dirty content-zod.ts)
- Docker Postgres: textbookagent-db-1 healthy on :5432 (`pg_isready` OK)

## What was implemented
- Persistent program docs under `docs/xplore-program/` (permanent invariants copied from ZIP)
- `BASELINE_REUSE_MANIFEST.json` + schema
- `CURRENT_ARCHITECTURE.md`
- Additive Print/Learn domain-boundary checker + tests
- Root script `program:phase00`
- No product feature behavior changes

## Existing systems reused
| System | Classification | Existing path | Action |
|---|---|---|---|
| Unit/concept/path | REUSE_AS_IS | apps/textbook-agent/backend/src/planning/ | Inventory only |
| Page Print | REUSE_AS_IS | planning/whole_lesson + packages/lectio-page | Inventory only |
| Component Learn generation | REUSE_AS_IS | Textbook agent generation/component_lectio/ | Inventory; Phase 01 import |
| Component library | REFACTOR | lectio-legacy-20260805/src/lib/lectio | Inventory; Phase 01 workspace |
| Builder | REUSE_AS_IS | frontend/src/lib/builder + backend/builder | Inventory only |
| DDD architecture guard | EXTEND | tools/agent/check_architecture.py | Left intact; added domain guard |
| Pre-cutover v3 Studio Component | REMOVE | generation/v3_studio (monorepo) | Do not restore as live Learn |
| LearnRelease/runtime/classes | NEW | (absent) | Later phases |

## New subsystems/files requiring justification
| New area | Existing seam inspected | Why extension was insufficient |
|---|---|---|
| `docs/xplore-program/*` | docs/implementation-runs (different program) | Need program-scoped state/manifest for Learn Expansion |
| `tools/xplore-program/check_domain_boundaries.py` | DDD layer guard | DDD guard does not enforce Print↔Learn package isolation |

## Files changed
- docs/xplore-program/** (new)
- tools/xplore-program/** (new)
- package.json (add `program:phase00`)

## Schema/migrations
None.

## Tests and verification
| Command / flow | Result | Evidence |
|---|---|---|
| `python -m pytest tools/xplore-program/tests -q` | PASS 5/5 | domain guard + manifest schema |
| `python tools/xplore-program/check_domain_boundaries.py` | PASS 0 violations | Print/Learn isolation |
| `pnpm --filter @lectio/page test` | PASS 41 | page package |
| `pnpm --filter @lectio/page check` | PASS 0 errors | page package |
| `pnpm --filter @lectio/page pdf:fixture` | PASS | teacher 6 / student 5 pages; report JSON; process hung after gate (pre-existing cleanup) |
| monorepo backend page+builder pytest | PASS 33 | page planners/writers + builder routes |
| frontend Page+Builder vitest | PASS 27 | document-version, LectioPageDocumentView, builder stores/route/toolbar |
| Textbook agent Component Lectio + builder pytest | PASS 83 | lifecycle/final_contract/prelive/runtime + builder |
| legacy `pnpm test` (lectio@0.6.0) | PRE-EXISTING FAIL | 111 passed; 1 timed out: `scripts/export-contracts.test.ts` (30s). Not introduced by Phase 00. Component render suite green. |
| Docker `pg_isready` | PASS | textbookagent-db-1 |

## Acceptance gates
- [x] Existing component generation/edit/reload path is demonstrably green or failures are precisely documented.
- [x] Existing page render/PDF path is demonstrably green or failures are precisely documented.
- [x] BASELINE_REUSE_MANIFEST.json exists and identifies canonical source/target paths.
- [x] PROGRAM_STATE.md exists in target repo.
- [x] No feature behavior changed.

## Architecture deviations
- Unattended 00–12 chaining (operator request) overrides ZIP one-conversation-per-phase guidance; still plan-before-implement and stop on BLOCKED/FAIL.
- Charter Textbook SHA updated from `8509233c` to actual `d2cf2f27`.
- Charter legacy branch name `master` vs actual `xplore` (SHA unchanged).

## Known limitations / deferred
- Monorepo lacks `component_lectio/` (Phase 01 import).
- Monorepo still hosts pre-cutover `v3_studio` Component path (REMOVE later; keep Print).
- Legacy contract-export test timeout is environmental/pre-existing.
- PDF fixture process may hang after successful gate (cleanup).

## Final state
- ending SHA: bd19a9060b637b84f6d86c002cbf01513adf1e4b (uncommitted Phase 00 artifacts)
- dirty state: prior untracked evidence/logs + new `docs/xplore-program/` + `tools/xplore-program/` + `package.json` script
- generated artifacts: docs/xplore-program/*, tools/xplore-program/*, packages/lectio-page/out PDFs from fixture
- safe to proceed to next phase: YES

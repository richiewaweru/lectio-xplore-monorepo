# Run 00 Report

## Result
DONE

## Baseline
- start SHA: `48c2cb4` (empty root init) → imports `aef04e5` / `8d5c8a7`
- branch: `pageobject-integration`
- Lectio source: `C:\Projects\lectio - Copy` @ `14ca43b5fac17f4c5a268eb626f3f96eac63a7be` (clean)
- Textbook xplore: `ba677486abe0b6090caaa570906a13244989899a`
- Legacy archive: `C:\Projects\lectio-legacy-20260805` (prior non-empty root, dirty `content-zod.ts` preserved)
- relevant pre-existing failures: none in focused baseline categories below; full backend suite (562 collected) not fully executed in one pass due to Windows SQLite lock from an interrupted prior run

## Implemented
- Renamed blocking `C:\Projects\lectio` → `lectio-legacy-20260805`
- History-preserving subtree import of `@lectio/page` and textbook-agent `xplore`
- Root workspace metadata (`package.json`, `pnpm-workspace.yaml`, `.gitignore`, lockfile)
- Authority pack copied to `docs/authority/xplore-pageobject-authority/`
- `BASELINE_MAP.md` resolving all 10 owners
- Provenance, progress, blockers files

## Files changed
| file | reason |
|---|---|
| `packages/lectio-page/**` | subtree import |
| `apps/textbook-agent/**` | subtree import |
| `package.json` / `pnpm-workspace.yaml` / `.gitignore` / `pnpm-lock.yaml` | monorepo workspace |
| `docs/implementation-runs/*` | RUN 00 evidence |
| `docs/authority/**` | on-disk authority pack |
| `scripts/*.ps1` | bootstrap/verify helpers |

## Verification
| command | result | evidence |
|---|---|---|
| `pnpm install` (root) | PASS | install completed; node_modules present |
| `pnpm --filter @lectio/page test` | PASS | 29 passed |
| `pnpm --filter @lectio/page check` | PASS | 0 errors |
| `pnpm --filter @lectio/page pdf:fixture` | PASS | `out/pdf-fixture-report.json` teacher 6 / student 5 pages |
| `pnpm --dir apps/textbook-agent/frontend test` | PASS | 317 passed / 76 files |
| `uv sync --all-extras` (backend) | PASS | exit 0 |
| `uv run pytest --collect-only -q` | PASS | 562 tests collected |
| `uv run pytest tests/planning tests/resource_specs tests/contracts -q` | PASS | 91 passed |

## Contract checks
- invariants checked: no product behavior edits; originals `lectio - Copy` untouched
- legacy behavior checked: imports only; v1 path unchanged

## Deviations
None architectural. Bootstrap script’s final provenance commit failed once on pathspec; provenance/workspace files committed in this RUN 00 completion commit. PDF fixture process hung after writing report; report JSON confirms gate green.

## Blockers / risks
- Root `pnpm.overrides` warning for frontend package.json (cosmetic)
- Full backend pytest single-pass still needs a clean machine lock; focused categories green

## Rollback
- commit(s): this RUN 00 commit + tag `pageobject-import-baseline`
- command: `git reset --hard pageobject-import-baseline` (after retag if needed)

## Next run readiness
READY for RUN 01 (`cursor-runs/RUN_01_CONTRACTS_AND_HEADINGS.md`)

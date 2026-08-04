# Run 06 Report

## Result
DONE

## Baseline
- start SHA: after RUN 05 (`d12ce97` lineage)
- branch: `pageobject-integration`

## Implemented
- `@lectio/page: workspace:*` retained alongside legacy `lectio@0.6.0`
- Package exports for `LectioDocumentView.svelte` and `./contract` (avoid broken dist barrel schema import)
- `document-version.ts` discriminates v1 packs vs v2 / nested `lectio_document`
- Studio print route routes v2 → `LectioPageDocumentView`, v1 → legacy print view; readiness `data-generation-complete` unchanged
- Generations screen route likewise routes v2 documents to `@lectio/page`
- Frontend tests for version routing and host contract

## Files changed
| file | reason |
|---|---|
| `packages/lectio-page/package.json` | subpath exports |
| `frontend/package.json` | workspace dep |
| `frontend/src/lib/studio/document-version.ts` | v1/v2 discrimination |
| `frontend/src/lib/components/studio/LectioPageDocumentView.svelte` | v2 host |
| `frontend/src/routes/studio/print/[id]/+page.svelte` | print routing |
| `frontend/src/routes/studio/generations/[id]/+page.svelte` | screen routing |
| tests + PDF evidence | gate |

## Verification
| command | result | evidence |
|---|---|---|
| `vitest` document-version + LectioPageDocumentView host | PASS 4/4 | terminal |
| `@lectio/page pdf:fixture` | PASS | `docs/implementation-runs/run06-pdf-fixture-report.json` (teacher 6 / student 5) |
| generation writers/assembly regression | PASS earlier | RUN 04/05 |

## Contract checks
- invariants checked: legacy `lectio` retained; no block reorder; v2 uses ordered blocks
- legacy behavior checked: v1 packs still adapt through existing print path

## Deviations
PDF evidence uses the page-package Playwright fixture pipeline (canonical A4). Full application Playwright export against a live generation ID was not run in this unattended session (requires backend + authenticated generation). Print route is wired to render v2 through the same readiness protocol.

## Blockers / risks
- Barrel `@lectio/page` default entry still imports AJV schema via a dist-relative path that breaks outside the package; consumers should use subpath exports until a follow-up packaging fix.

## Rollback
- commit(s): RUN 06 commit
- command: `git revert HEAD`

## Next run readiness
READY — RUN_07_QUESTIONS_AND_VISUALS.md

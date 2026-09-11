# Final Acceptance Matrix

## A. Prompt/spec system
- [x] learner-action policy is file-backed
- [x] document composer prompt is manifest-backed
- [x] document writer prompt is manifest-backed
- [x] interaction selection/authoring policy is file-backed
- [x] figure authoring guidance is file-backed
- [x] Print realization guidance is file-backed
- [x] effective prompt hashes are traceable
- [x] Markdown default change alters effective hash without Python edits

## B. Teaching Plan
Fresh Unit #1:
- [x] natural learner action during instruction
- [x] natural learner action during check/practice
- [x] no native UI/form ids

Fresh Unit #2:
- [x] different concept/knowledge shape
- [x] action density is reasonable
- [x] passive blocks still exist when sensible

## C. Twin path fidelity
- [x] `select-one` → Learn choice
- [x] `select-one` → Print choices
- [x] second action → appropriate Learn interaction
- [x] same action → appropriate Print response
- [x] no learner action → no independently invented task divergence

## D. Shared writing
- [x] Learn ordinary nodes use shared writer
- [x] live Unit Print ordinary nodes use shared writer
- [x] Figure uses visual pipeline
- [x] Print-specific treatment happens downstream
- [x] no duplicate ordinary authoring path remains canonical

## E. Path admission
- [x] explicit realize-learn
- [x] explicit realize-print
- [x] Learn-first then Print works
- [x] Print-first then Learn works
- [x] no artifact conversion
- [x] no re-approval/stale-revision workaround

## F. Learn assets/sections/UI
- [x] generated figure URL returns 200
- [x] section metadata survives realization
- [x] tabs/navigation use realized section metadata
- [x] edit/add/delete/reorder/save/reload works
- [x] local section/node regeneration targets intended scope

## G. Learn runtime
At least two naturally generated interaction types in live Units:
- [x] generate
- [x] render
- [x] submit
- [x] evaluate
- [x] attempt state persists/reloads

All retained kinds:
- [x] fixture/script generation
- [x] schema validation
- [x] renderer
- [x] evaluator
- [x] persistence contract

## H. Print editor
- [x] native LectioDocument v2 view/edit toggle
- [x] edit prose
- [x] edit table/list/callout
- [x] edit question/response treatment as supported
- [x] edit figure metadata/asset as supported
- [x] save increments revision
- [x] stale edit returns 409
- [x] reload shows edit
- [x] PDF reflects edit
- [x] Learn sibling unchanged

## I. Degraded/failure behavior
- [x] LLM composition mode recorded
- [x] heuristic fallback visible, never silent
- [x] writer retry stage-local
- [x] interaction retry stage-local
- [x] figure retry stage-local
- [x] failed required live proof → BLOCKED/FAIL, never PASS

## J. Repository health
- [x] backend affected suites
- [x] frontend tests/checks
- [x] contracts checks *(re-run green on Treasure Joe Final Cleanup Phase F: `pnpm contracts:test` + `pnpm contracts:check`)*
- [x] page checks
- [x] app tests *(Unit/Print page vitest; Treasure Joe F re-green after loopback/401 test alignment)*
- [x] domain/architecture guards
- [x] no stale package/import path
- [x] no production stub/TODO on canonical flow

## Treasure Joe re-proofs (2026-09-11)
- [x] G exact Unit → Generate Learn → Builder → evaluate → persisted attempt (`docs/treasure-joe-final-cleanup/evidence/phase-d-PASS.json`)
- [x] H PDF bytes contain edit marker + stale 409 + Learn sibling unchanged (`docs/treasure-joe-final-cleanup/evidence/phase-e-PASS.json`)
- [ ] Full `validate_repo.py --scope backend` remains red on pre-existing ruff + planning suite debt (not claimed PASS)

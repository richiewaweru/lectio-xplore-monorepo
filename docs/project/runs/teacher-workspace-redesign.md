# Teacher Workspace Redesign Run

**Classification**: major
**Subsystems**: backend and frontend

## Phase 0 Live Baseline — 2026-07-27

The authenticated production application was inspected in the Codex in-app browser before code changes.

- The legacy dashboard rendered the profile, Studio and Builder cards, pack history, Builder lessons, and pre-Builder generations on one canvas.
- The dashboard's current `lessonStatus()` labelled every matched non-`completed`/non-`failed` history item as `streaming`.
- Several generated `photosynthesis` lessons therefore rendered as indistinguishable streaming rows.
- `/builder` additionally exposed exact `updated_at` values and whether each lesson came from a template or generation.
- The generated lesson “How stomata regulate gas exchange and water loss” rendered a complete five-section document while Builder showed five unresolved issues. The dashboard still labelled its matched row `streaming`.
- Builder persisted section-level review issues under each section's `meta.issues`; unresolved document-level generation issues were derived from `booklet_issues` and filtered by the existing `lectio:dismissed-doc-issues:{lessonId}` key.

### State distinguishability

| State | Distinguishable before redesign? | Live evidence |
| --- | --- | --- |
| `writing` | Partially | Nonterminal generation history is labelled `streaming`, but the label also catches terminal-with-review cases. |
| `attention` | No | Unresolved issues are visible inside Builder but are absent from the dashboard row. |
| `ready` | Partially | A completed generation can be recognized, but the dashboard does not exclude unresolved review flags. |
| `draft` | Yes | Lessons without a matched active/completed generation render as `draft`. |

The browser-control surface exposed rendered DOM and console logs but not authenticated XHR bodies or performance entries. A direct same-origin read was unavailable because page-scope `fetch` and `performance` are intentionally disabled, and the stored bearer token was not inspected. Raw response capture therefore remains a manual DevTools verification item before deployment; implementation relies only on the existing checked-in `/api/v1/builder/lessons`, `/api/v1/v3/generations`, document, and thin status contracts.

## Progress

- [x] Reproduced current dashboard, Builder list, active-generation labels, and unresolved review state
- [x] Phase 1 — optional class label
- [x] Phase 2 — pure lesson state
- [x] Phase 3 — flag-gated lessons surface
- [x] Phase 4 — live progress and review counts
- [x] Phase 5 — settings and deletion
- [x] Phase 6 — permanent workspace cutover and legacy retirement
- [x] Repository validation and self-review recorded

## Validation Evidence

- Phase 1 backend Builder routes: 14 passed
- Phase 1 Studio/component tests: 33 passed
- Phase 1 frontend type check: 0 errors, 0 warnings
- Phase 1 Ruff: passed
- Phase 2 lesson-state and generation-adapter tests: 8 passed
- Phase 2 frontend type check: 0 errors, 0 warnings
- Phase 3 lessons and landing-route tests: 4 passed
- Phase 3 frontend type check: 0 errors, 0 warnings
- Phase 4 poller, lessons transition, and Studio regression tests: 32 passed
- Phase 4 frontend type check: 0 errors, 0 warnings
- Phase 5 dashboard, settings, and deletion tests: 14 passed
- Phase 5 frontend type check: 0 errors, 0 warnings
- Production frontend build: passed
- Repository architecture check: no violations
- Final `git diff --check`: passed; worktree clean
- Full frontend Vitest run: inconclusive after reaching the 10-minute execution cap without emitting a failing test
- Full repository validation script: inconclusive after reaching the 5-minute execution cap
- Phase 6 affected frontend routes and helpers: 53 passed
- Phase 6 backend Builder regression suite: 14 passed
- Phase 6 frontend type check: 0 errors, 0 warnings
- Phase 6 production frontend build: passed
- Phase 6 repository architecture check: no violations
- Phase 6 required source and repository grep checkpoints: zero hits
- Phase 6 full repository validation script: inconclusive after reaching the 10-minute execution cap without emitting a failing check
- Browser verification before push: the deployed Phase 5 `/lessons` remained authenticated and visually responsive at 375px with no visible horizontal overflow; Phase 6 routing, split-button, shell, and Studio handoff require post-deployment verification

## Risks and Follow-up

- Run the authenticated Phase 6 end-to-end browser flow after this commit is pushed and the deployment completes.
- Capture the two authenticated JSON response bodies and network waterfall manually before production rollout.

# Deferred nonessential and aesthetic work

Date: 2026-08-12

This list intentionally excludes defects that can corrupt generation state, rerun
expensive stages, weaken native-only routing, invalidate reload hashes, or produce
incorrect assessment/diagram content. Those remain core work.

## Safe to hand to a lower-cost agent

- Improve long lesson-title presentation in the completed viewer. The current
  heading can look abruptly truncated or wrap awkwardly, but the persisted lesson
  objective and document contract remain intact.
- Refine spacing, typography, pill styling, and responsive layout for the
  deterministic diagram label band. Do not change label identity, deduplication,
  topology, QC, cache, or hash behavior.
- Improve the visual treatment of topology nodes, arrows, icons, colors, and the
  low-frequency provider-derived background. Do not infer relationships from label
  order or add subject-specific branches.
- Improve progress/retry wording and loading feedback in Studio. Preserve the
  authoritative `next_action` and native retry endpoint; never infer retryability
  from display text.
- Polish the ready-with-quality-warning banner and button copy. Continue reading
  only the explicit native `visual_quality` DTO; do not inspect legacy report JSON.
- Clean up harmless CSS warnings or unused selectors if they reappear. Require the
  frontend type check and focused page tests afterward.
- Improve evidence-report formatting, screenshots, filenames, and navigation.
  Historical evidence must be appended to, never rewritten as a successful run.

## Compatibility cleanup, not an immediate product blocker

- `report_json` still contains historical booklet summary fields such as
  `streaming_preview`, stale section counts, and export flags. Native Studio and
  native PDF export use the V2 document/status contracts instead. Any cleanup must
  preserve that authority split and should be handled as an explicit compatibility
  migration, not a UI patch.
- The fixed legacy `AnchorUsage` projection does not model every procedural slot
  name. Authoritative block briefs carry anchor reuse, so this is schema cleanup,
  not a reason to reopen the teaching plan during the stability goal.

## Not safe to delegate as aesthetics

- Do not change native-only routing, generation provenance, contract-v2 approval,
  retry state transitions, execution leases, reload hashes, PDF edition behavior,
  assessment ownership, visual QC, accepted-only caching, or topology validation.
- Do not make another xAI/image-provider call for generation
  `5222366a-8308-43e6-bb6c-4e4a0697f1d9` while credits are being conserved.
- The current Water Cycle generation remains `awaiting_visuals`. Its deterministic
  topology recovery is covered by mocked tests but has not received the final live
  topology-planner/QC acceptance run. Do not describe it as final M7 evidence.

## Verification recorded before handoff

- Deterministic topology/schema/renderer/recovery/dispatch/failure gate:
  **36 passed**, one existing Pydantic warning.
- Focused topology recovery + dispatch rerun after the label-map integration fix:
  **13 passed**.
- Ruff on the topology planner, renderer, recovery, dispatch, and focused tests:
  **passed**.
- No live LLM, xAI, image-provider, or browser generation call was made for these
  final verification commands.

## Final credit-safe audit (2026-08-12)

- Ports 8000 and 5173 were listening during the audit.
- Frontend `pnpm check`: **0 errors, 0 warnings**.
- Essential backend slice (native-only routing, legacy shutdown, native PDF,
  topology recovery, deterministic renderer): **20 passed**, one existing Pydantic
  warning.
- No provider, LLM, image, or browser generation call was made.

## Final source-truth boundary audit (2026-08-12)

- Topology recovery now derives its source digest and planner input from the
  persisted teaching block, lesson objective, scope, terminology, exclusions,
  and anchor; it no longer uses truncated figure caption/alt text as the
  authoritative source.
- The dispatch boundary passes that structured snapshot into recovery and
  still removes the request from ordinary visual-provider dispatch.
- Focused topology/dispatch/rendering suite: **36 passed**, one existing
  Pydantic warning.
- Targeted Ruff and diff checks passed. No external provider call was made.

## Current deterministic acceptance rerun (2026-08-12)

- Native hardening/recovery command from `PLAN.md`: **157 passed**, one existing
  Pydantic warning.
- Delivery PDF/telemetry command from `PLAN.md`: **11 passed**, one existing
  Pydantic warning.
- Studio, completed viewer, and print frontend tests: **37 passed**.
- The topology recovery source fence now includes the authoritative label map and
  explicit evidence-key allowlist; unknown planner evidence remains fail-closed.
- No provider, browser-generation, or database-mutation operation was used for
  this rerun. Live M7 acceptance and the four-run final matrix remain open.

## Repository-wide refresh (2026-08-12)

- Architecture validator: **no violations**.
- Backend Ruff: **passed**.
- Full backend suite after the structural-repair fixture contract update:
  **1,080 passed**, one existing Pydantic warning.
- Frontend type check: **0 errors, 0 warnings**.
- Frontend production build: **passed**; only existing Rollup/chunk-size warnings.
- Tooling tests: **8 passed**.
- Services remain on the required ports 8000 and 5173.
- Live authenticated/provider acceptance is still intentionally outstanding and
  must not be inferred from deterministic results.

## Authenticated viewer truthfulness check (2026-08-12)

- The existing signed-in native viewer for Water Cycle generation
  `5222366a-8308-43e6-bb6c-4e4a0697f1d9` was inspected read-only in the browser.
- The V2 document loaded, but its authoritative visual state was not final. The
  viewer now shows **“The lesson is not final yet”**, exposes **Retry visuals**,
  and disables PDF export instead of presenting the unavailable figure as a
  final-ready lesson.
- Focused completed-viewer tests: **8 passed**; Svelte diagnostics: **0 errors,
  0 warnings**.
- No retry click, provider call, database mutation, or hidden progression was
  performed.

## Full frontend regression refresh (2026-08-12)

- Full frontend Vitest suite after the pending-visual viewer correction:
  **80 files, 338 tests passed**.
- Frontend production build completed successfully. Existing Rollup annotation,
  optional-dependency, and chunk-size warnings remain non-fatal.
- The viewer correction is therefore covered both by focused tests and the full
  frontend suite; no provider or generation action was triggered.

## Authenticated Home route check (2026-08-12)

- The signed-in browser opened `http://127.0.0.1:5173/units` successfully.
- The visible workspace heading is **Units**, with the native `+ New unit` entry
  and native unit links.
- No Builder link, legacy creation action, or blank Studio creation surface was
  visible in the authenticated Home DOM.
- This was read-only: the New unit action was not clicked, so no generation or
  provider call was started.

## Read-only route quarantine check (2026-08-12)

- Authenticated `/lessons` settled at `/units` and displayed the Units workspace.
- Authenticated blank `/studio` settled at `/units` and did not expose a plan,
  create, or generation surface.
- These route checks caused no generation, provider call, or database mutation.

## Native print readiness boundary (2026-08-12)

- Native V2 print now consults generation detail before rendering. Pending,
  failed, or flagged visual work produces a clear print error and does not
  present a partial lesson as final; legacy V3 print keeps its existing adapter
  path.
- Focused print/viewer tests: **10 passed**; Svelte diagnostics: **0 errors,
  0 warnings**.
- Services remained healthy on ports 8000 and 5173. No provider call or
  generation mutation was made.

## Deterministic topology fallback verification (2026-08-12)

- Provider-free topology schema, checkpoint/recovery, dispatch integration,
  compositor/renderer, and visual executor tests: **45 passed**, one existing
  Pydantic warning.
- Targeted Ruff checks passed for the topology, renderer, compositor, storage,
  dispatch, executor, and related tests.
- No image-provider call, retry click, generation mutation, or database write
  was made. The live Water Cycle remains intentionally unresolved and is not
  counted as final acceptance evidence.

## Repository-wide acceptance refresh (2026-08-12)

- Architecture check: **no violations**.
- Backend Ruff: **passed**.
- Full backend suite: **1,080 passed**, one existing Pydantic warning.
- Frontend type check: **0 errors, 0 warnings**.
- Frontend production build: **passed** with only existing nonfatal Rollup
  annotation, optional-dependency, and chunk-size warnings.
- Tooling suite: **8 passed**.
- This refresh used no provider calls and did not mutate generations or the
  database.

## Worker reclaim evidence review (2026-08-12)

- The existing superseding native run report records a real worker death,
  lease expiry, restart, token increase (`1 -> 2`), reclaim event, and
  checkpoint continuation without manual database edits:
  `RECOVERY_RUN_5C254377.md`.
- The report also records old/new owner IDs, listener PID, app-instance IDs,
  heartbeat/expiry timestamps, and the stale-owner write boundary. It is
  retained as targeted evidence for Sol review; it is not being relabeled as a
  final-matrix run.
- Current deterministic lease/fencing/restart regressions: **87 passed**, one
  existing Pydantic warning.
- No new worker was killed, no provider call was made, and no generation or
  database state was changed during this review.

## Current authenticated Home/New-unit replay (2026-08-12)

- Signed-in browser Home is `/units` and shows only native unit records and
  Settings navigation; no Builder or legacy creation link is visible.
- Opening `+ New unit` shows the native Subject / Grade level / teaching brief
  form and a `Plan it` action. The form was closed without submission, so no
  unit, generation, provider call, or database mutation occurred.
- This replay confirms the current creation surface is native, but it is not a
  full lesson completion or final-matrix proof.

## Token-aware native print guard (2026-08-12)

- The native print readiness lookup now reuses the route's existing bearer
  token headers. Tokenized print links therefore authenticate both the V2
  document request and the native generation-detail readiness check.
- Focused print route tests: **2 passed**; Svelte diagnostics: **0 errors,
  0 warnings**.
- Pending/flagged native visuals still fail closed for print; no provider call
  or generation mutation was made.

## Authenticated print replay and auth-client fix (2026-08-12)

- Browser replay initially exposed a real defect: the print route used raw
  `fetch`, so a signed-in session without a `token=` query parameter received
  `401` even though Studio was authenticated.
- The route now uses the shared `apiFetch` client for both document and native
  generation-detail requests, while preserving explicit query-token headers.
- Focused print test: **2 passed**; Svelte diagnostics: **0 errors, 0
  warnings**.
- Authenticated replay now reaches the intended guard: **“Native visuals are
  not ready for print. Retry visuals from Studio before exporting.”** The
  browser was returned to `/units`; no retry, provider call, or generation
  mutation occurred.

## Safe-to-defer aesthetics and cleanup (2026-08-12)

These are intentionally outside the essential stability contract and may be
handled later by a small cleanup agent:

- typography, spacing, color, shadows, and non-functional responsive polish;
- copy-editing labels, helper text, and empty-state wording after behavior is
  accepted;
- icon/illustration substitutions that do not change asset contracts;
- loading shimmer, transition timing, and other animation polish;
- diagnostics-panel layout and developer-only visual affordances;
- bundle/chunk-size optimization and warning cleanup when no runtime behavior
  changes;
- test fixture naming, evidence prose formatting, and other documentation
  cosmetics.

Do not defer routing/auth boundaries, native-v2 contract validation, retry and
lease ownership, visual-QC/cache behavior, topology validation, hash/reload
proof, PDF readiness, assessment ownership, or telemetry attribution: those
remain core correctness work.

## Latest provider-free visual core verification (2026-08-12)

- Topology schemas/planner/recovery, deterministic renderer/compositor, visual
  dispatch, and visual execution focused suites: **69 passed**, one existing
  Pydantic warning.
- Ruff on the touched topology/visual modules and tests: **passed**.
- Python compilation of the touched topology/compositor modules: **passed**.
- Frontend/backend services remained healthy on ports 5173 and 8000 (HTTP 200).
- No provider call, retry click, generation mutation, or database write was made.

## Final native boundary pass (2026-08-12)

- Backend native routing/status/retry/legacy-shutdown/PDF boundary: **67 passed**,
  one existing Pydantic warning.
- Frontend Studio/viewer/print/auth boundary: **41 passed**.
- Backend/frontend services remain healthy on ports 8000 and 5173.
- No provider call, retry click, generation mutation, or database write was made.

## Cross-layer native print/export regression (2026-08-12)

- Backend native visual/PDF/export guards: **20 passed**, one existing Pydantic
  warning.
- Frontend print/viewer/API regression: **24 passed**.
- The combined boundary proves authenticated native print requests, native V2
  readiness gating, edition-aware rendering, malformed-native fail-closed
  behavior, and backend export readiness checks remain aligned.
- No provider call or generation/database mutation was made.

## Full frontend regression after print auth fix (2026-08-12)

- Full frontend Vitest suite: **80 files, 339 tests passed**.
- This includes the token-aware native print route, native viewer status,
  routing/quarantine, API, Builder compatibility, and component suites.
- No provider call or generation/database mutation was made.

## Explicit print-token precedence regression (2026-08-12)

- Shared `apiFetch` now preserves an explicit `Authorization` header and only
  falls back to the stored session token when no header is supplied. This keeps
  tokenized print links correct even if a stale session token is present.
- Added focused client coverage for both explicit-token and stored-session-token
  paths: **4 tests passed** with the native print route.
- Svelte diagnostics: **0 errors, 0 warnings**.
- No provider call or generation/database mutation was made.

## Full frontend regression after API auth precedence fix (2026-08-12)

- Full frontend Vitest suite: **81 files, 341 tests passed**.
- This includes the new shared `apiFetch` explicit-token precedence coverage,
  native print/viewer routes, and all existing product/compatibility suites.
- Svelte diagnostics remain **0 errors, 0 warnings**.
- No provider call or generation/database mutation was made.

## Final acceptance audit (2026-08-12)

- Added `FINAL_ACCEPTANCE_AUDIT.md`, mapping each PLAN acceptance requirement
  to reviewed evidence and explicitly listing the remaining live-provider and
  final-matrix gaps.
- Current verdict remains **NOT YET STABLE**: deterministic implementation and
  native-only UI contracts are green, but live accepted visual/PDF proof and
  four new browser-driven matrix runs are not present.

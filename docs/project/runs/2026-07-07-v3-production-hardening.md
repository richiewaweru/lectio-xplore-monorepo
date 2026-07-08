# V3 Production Hardening Progress

Source handoff: `C:\Users\richi\Downloads\v3-production-hardening-handoff.md`

## Feature: V3 Production Hardening

**Classification**: major
**Subsystems**: backend, frontend, infrastructure
**Draft PR**: https://github.com/richiewaweru/text-book-generator/pull/92

### Progress
- [x] Understood requirements and identified scope
- [x] Read project onboarding, workflow, and standards
- [x] Ran baseline validation before new changes
- [x] Resolve/report red baseline before starting implementation
- [x] Phase 1: Verify image URL permanence
- [x] Phase 2: CSP img-src + image health probe
- [x] Phase 3: Streaming/schema bugs
- [x] Phase 4: Async image client + real visual concurrency
- [x] Phase 5: Image quality gate
- [x] Phase 6: must_show/must_not_show + raster visual style
- [x] Phase 7: Print preflight endpoint + builder surfacing
- [x] Phase 8: Per-visual regenerate endpoint
- [x] Phase 9: Content-hash image caching
- [x] Phase 10: Block-writer slots + manual-only contract
- [x] Final integration pass
- [x] Self-reviewed against `agents/standards/review.md`
- [x] Wrote commit message(s) following `agents/standards/communication.md`
- [x] Noted follow-up work or blockers

### Validation Evidence
- Baseline backend, first run: `uv run pytest -q` failed (`83 failed, 225 passed, 1 warning`) because the process loaded the repo-root `.env`; `LECTIO_CONTRACTS_DIR` pointed at a container path, and SQLite also reported lock errors.
- Baseline frontend check: `npm run check` passed (`0 errors, 0 warnings`).
- Baseline backend, local env rerun: with `LECTIO_CONTRACTS_DIR` set to `backend/contracts`, `uv run pytest -q` still failed (`32 failed, 276 passed, 1 warning`). Major remaining causes: FastAPI startup migrations attempt SQLite constraint alters, shared SQLite test DB lock errors, and one existing visual-executor log assertion failure.
- Baseline frontend tests: `npm test` failed (`1 failed, 49 passed`; `187 passed`, `1 failed`) because `src/lib/no-vendor-lectio-imports.test.ts` exceeded the 5000ms Vitest timeout.
- Baseline backend, corrected local env: `LECTIO_CONTRACTS_DIR=backend/contracts RUN_MIGRATIONS_ON_STARTUP=false uv run pytest -q` passed (`308 passed, 1 warning`).
- Baseline frontend, timeout-adjusted rerun: `npm test -- --testTimeout=30000` passed (`50 passed`, `188 passed`). The vendor import guard took about 4.9s, so the default 5s test timeout is tight on this machine.
- Baseline frontend check rerun: `npm run check` passed (`0 errors, 0 warnings`).
- Phase 2/diagnostic targeted: `uv run pytest tests/core/health/test_health_routes.py tests/media/test_v3_image_pipeline_diagnostic.py -q` passed (`15 passed, 1 warning`).
- Phase 3 targeted: skeleton/schema checks passed:
  - `uv run pytest tests/v3_execution/test_v3_execution_core.py::test_runner_emits_skeleton_ready_before_component_events tests/generation/test_v3_studio_generation_stream.py::test_v3_document_endpoint_returns_persisted_skeleton_document -q` (`2 passed, 1 warning`)
  - `uv run pytest tests/v3_review/test_v3_review_deterministic.py tests/v3_execution/test_section_builder_tolerant.py::test_component_order_metadata_matches_emitted_component_sequence -q` (`8 passed, 1 warning`)
- Phase 4 targeted: `uv run pytest tests/media/test_providers_registry.py tests/media/test_v3_image_pipeline_diagnostic.py tests/core/health/test_health_routes.py -q` passed (`27 passed, 1 warning`).
- Phase 4 lint: `uv run ruff check src/media/providers/openai_image_client.py src/media/providers/xai_image_client.py src/v3_execution/config/concurrency.py tests/media/test_providers_registry.py src/app.py src/core/storage/gcs_image_store.py tests/core/health/test_health_routes.py` passed.
- Phase 4 grep checkpoint: `rg "urllib.request.urlopen" backend/src/media/providers -n` returned no matches.
- Phase 5 targeted: `uv run pytest tests/v3_execution/test_v3_execution_core.py tests/v3_review/test_v3_review_deterministic.py tests/media/test_providers_registry.py -q` passed (`35 passed, 1 warning`).
- Phase 5 lint: `uv run ruff check src/media/qc src/v3_execution/executors/visual_executor.py src/v3_execution/models.py src/v3_execution/runtime/validation.py src/v3_execution/config/models.py src/v3_execution/config/__init__.py src/v3_review/deterministic_checks.py tests/v3_execution/test_v3_execution_core.py tests/v3_review/test_v3_review_deterministic.py` passed.
- Phase 5 frontend check: `npm run check` passed (`0 errors, 0 warnings`).
- Phase 5 frontend targeted: `npm test -- src/routes/studio/page.test.ts --testTimeout=30000` passed (`17 passed`).
- Phase 5 backend full suite: after creating shared SQLite test schema with `Base.metadata.create_all()` and running with `LECTIO_CONTRACTS_DIR=backend/contracts RUN_MIGRATIONS_ON_STARTUP=false`, `uv run pytest -q` passed (`314 passed, 1 warning`).
- Phase 5 frontend full suite: `npm test -- --testTimeout=30000` passed (`50 files`, `188 passed`).
- Phase 6 targeted: `uv run pytest tests/v3_blueprint/planning/test_assembler.py tests/v3_blueprint/planning/test_section_expander_prompt.py tests/v3_execution/test_compile_orders_series_frames.py tests/v3_execution/test_visual_prompt_style.py tests/v3_execution/test_v3_execution_core.py tests/v3_review/test_v3_review_deterministic.py -q` passed (`34 passed, 1 warning`).
- Phase 6 lint: `uv run ruff check src/v3_blueprint/models.py src/v3_blueprint/planning/models.py src/v3_blueprint/planning/assembler.py src/v3_blueprint/planning/section_expander.py src/v3_execution/models.py src/v3_execution/compile_orders.py src/v3_execution/prompts/visual_executor.py tests/v3_blueprint/planning/test_assembler.py tests/v3_blueprint/planning/test_section_expander_prompt.py tests/v3_execution/test_compile_orders_series_frames.py tests/v3_execution/test_visual_prompt_style.py` passed.
- Phase 7 backend targeted: `uv run pytest tests/routes/test_builder_lessons.py -q` passed (`13 passed, 1 warning`).
- Phase 7 backend lint: `uv run ruff check src/core/pdf_export_runtime.py src/generation/pdf_export/rendering/playwright.py src/builder/routes.py tests/routes/test_builder_lessons.py` passed.
- Phase 7 frontend targeted: `npx vitest run src/lib/builder/components/toolbar/DocumentToolbar.test.ts --testTimeout=30000 --pool=threads --reporter=dot` passed (`5 passed`). Note: the default forks pool stalled without output in this session.
- Phase 7 frontend check: `npm run check` passed (`0 errors, 0 warnings`).
- Phase 8 targeted: `uv run pytest tests/generation/test_v3_studio_generation_stream.py::test_v3_visual_regenerate_replaces_visual_block_and_section_diagram tests/generation/test_v3_studio_generation_stream.py::test_v3_visual_regenerate_returns_404_for_unknown_visual tests/generation/test_v3_studio_generation_stream.py::test_v3_visual_regenerate_returns_409_when_generation_lock_busy -q` passed (`3 passed, 1 warning`).
- Phase 8 lint: `uv run ruff check src/generation/v3_studio/router.py tests/generation/test_v3_studio_generation_stream.py` passed.
- Phase 9 targeted: `uv run pytest tests/v3_execution/test_v3_execution_core.py::test_visual_cache_key_is_stable_and_includes_constraints tests/v3_execution/test_v3_execution_core.py::test_execute_visual_cache_hit_skips_provider_and_copies_cached_image tests/v3_execution/test_v3_execution_core.py::test_execute_visual_cache_miss_uploads_generation_and_cache_objects tests/generation/test_v3_studio_generation_stream.py::test_v3_visual_regenerate_replaces_visual_block_and_section_diagram -q` passed (`4 passed, 1 warning`).
- Phase 9 lint: `uv run ruff check src/v3_execution/executors/visual_executor.py src/media/storage/image_store.py src/core/storage/gcs_image_store.py src/generation/v3_studio/router.py tests/v3_execution/test_v3_execution_core.py tests/conftest.py` passed.
- Phase 10 targeted: `uv run pytest tests/routes/test_blocks_generate.py::test_run_block_generation_uses_dedicated_block_writer_nodes tests/routes/test_blocks_generate.py::test_run_block_generation_rejects_manual_only_component tests/v3_review/test_v3_review_deterministic.py::test_manual_only_component_emits_major_issue -q` passed (`3 passed, 1 warning`).
- Phase 10 lint: `uv run ruff check src/generation/block_generate.py src/v3_execution/config/models.py src/v3_execution/config/__init__.py src/contracts/lectio.py src/v3_review/deterministic_checks.py src/v3_review/reviewer.py tests/routes/test_blocks_generate.py tests/v3_review/test_v3_review_deterministic.py` passed.
- Phase 10 grep: `rg "V3_ANSWER_KEY_GENERATOR" backend/src/generation/block_generate.py -n` returned no matches; `rg "MANUAL_ONLY_COMPONENT_IDS" backend/src -n` returned contract + reviewer + block generation call sites.
- Phase 1 Railway env check: production Railway service `text-book-generator Copy Copy` has `GCS_IMAGE_BASE_URL` set; a Railway console env-shape probe printed `GCS_IMAGE_BASE_URL_set= True` and `GCS_IMAGE_BASE_URL_host= storage.googleapis.com` without printing the full value.
- Phase 1 production stored-pack check: read-only Railway console DB probe scanned the 10 most recent `generations.document_json` rows with stored JSON. Result: `rows_checked=10`, `total_image_urls=8`, `total_signed_marker_urls=0`. The one row with image URLs had `signed_markers=0`; the remaining checked rows had no image URL fields.
- Final Railway env shape check: production currently reports `V3_CONCURRENCY_VISUAL_MAX=2`; `V3_VISUAL_QC_ENABLED`, `V3_IMAGE_CACHE_ENABLED`, and `V3_VISUAL_QC_*` provider/model/API-key/base-url overrides are unset. Local code defaults cover the new flags after deploy, but the handoff-requested production concurrency update to 4 is still pending.
- Final backend full suite attempt 1: with seeded shared SQLite runtime DB, `uv run pytest -q` failed with SQLite `database is locked` across V3 generation writer/studio DB tests after `299 passed, 30 failed, 1 warning` in 4m40s. Failures were lock errors, not assertion failures.
- Final backend full suite attempt 2: reran against a fresh temp SQLite DB file; command exceeded the 5-minute tool timeout before producing a summary.
- Final backend isolated V3 DB tests: reran V3 database-sensitive tests against a fresh temp SQLite DB and they passed (`33 passed, 1 warning`).
- Final backend full suite: reran `uv run pytest -q` against a fresh temp SQLite DB with the local contracts path and migrations disabled; passed (`329 passed, 1 warning in 105.69s`).
- Final frontend check: `npm run check` passed (`0 errors, 0 warnings`).
- Final frontend vendor guard fix: added a local 30s timeout to `src/lib/no-vendor-lectio-imports.test.ts` because the guard takes about 6s under the full parallel suite on this machine.
- Final frontend full tests: `npm test` passed (`50 passed`, `189 passed`) in 489.88s.
- Final frontend build: `npm run build` passed; SvelteKit/Vite built SSR and client output successfully, with the existing large-chunk warning.
- Final architecture check: `python tools\agent\check_architecture.py --format text` passed (`No architecture violations found.`).
- Final whitespace check: `git diff --check` passed.
- CI follow-up backend lint: removed an unused diagnostic import after GitHub `backend-quality` reported `F401`; `uv run ruff check src/ tests/` passed.
- CI follow-up backend tests: made pytest pin `LECTIO_CONTRACTS_DIR` to `backend/contracts`, disable SQLite startup migrations, provide dummy provider keys for mocked LLM tests, and create the shared SQLite runtime schema at session start; `uv run python ../tools/agent/validate_repo.py --context docs/project/context-summary.yaml --scope backend` passed (`backend-ruff` pass; `backend-pytest` pass; `329 passed, 1 warning in 110.70s`).
- CI follow-up frontend lockfile sync: pinned `lectio` to `0.5.0` in `package.json`, `package-lock.json`, and `pnpm-lock.yaml`; local lockfile sync check printed `Lectio lockfiles are in sync at 0.5.0`.
- CI follow-up frontend validation: local frontend validator wrapper could not run because `yaml` is unavailable in the frontend uv context, so commands were run directly. `npm run check` passed (`0 errors, 0 warnings`), `npm test -- --run` passed (`50 passed`, `189 passed`), and `npm run build` passed with the existing large-chunk warning.
- 2026-07-08 resume check: worktree was clean, PR #92 remained merge-clean with successful backend/frontend/lockfile/Vercel checks at head `09adc6d`. Railway CLI remained unauthenticated (`Unauthorized. Please login with railway login`). Chrome could list the open Railway service tab but timed out claiming it; `npx @railway/cli login` and `npx @railway/cli login --browserless` did not yield a usable authenticated session or visible device code from this shell.
- 2026-07-08 Railway env update: linked CLI to project `efficient-acceptance`, production environment, backend service `text-book-generator Copy Copy`. Verified `GCS_IMAGE_BASE_URL` was set, then set `V3_CONCURRENCY_VISUAL_MAX=4`, `V3_VISUAL_QC_ENABLED=true`, and `V3_IMAGE_CACHE_ENABLED=true` with deploys skipped before the final deploy.
- 2026-07-08 Railway deploy: first detached upload created deployment `cd2c2774-3ad1-4752-ab92-ad3ec7d614a8` and failed before an associated build existed; public health briefly returned 404 after removing the stale deployment record. Retried with streamed CI logs and deployed `70647ec4-cd6b-48a0-93e7-0afaa1ecf6b8` successfully from local commit `5dc939b`. Railway service status reported `SUCCESS`, `stopped=false`; `/health/ready` returned 200 with a fresh instance uptime.
- 2026-07-08 production image probe: `POST https://text-book-generator-copy-copy-production.up.railway.app/health/image/probe` returned 200 with `grok_imagine_only=ok`, `v3_gcs_upload_only=ok`, and `probe_image_bytes=91639`. Deployment logs showed startup without the production image-store signed-URL warning.
- Real-provider image/QC diagnostic follow-up: initial no-cache local diagnostic exposed `v3_visual_qc` inheriting `V3_FAST_*` DeepSeek config and then an oversized `max_tokens=120000` Anthropic request, both of which caused QC fail-open. Fixed `v3_visual_qc` to keep an Anthropic vision-capable node default unless `V3_VISUAL_QC_*` explicitly overrides it, and capped the QC verdict call at `max_tokens=512`. Rerunning `V3_IMAGE_CACHE_ENABLED=false uv run python scripts/diagnose_v3_image_pipeline.py --env-file .env` passed all probes; Anthropic returned 200 for QC and the visual completed `status=ready`.
- Full local V3 route smoke attempt: started a small real-provider generation from `david_parallel_circuits.json` through the ASGI app; `/api/v1/v3/generate/start` returned 200 and the SSE stream emitted `generation_started`. The run did not reach document/export/preflight locally because the loaded `.env` database host failed DNS resolution while snapshot/detail reads attempted to connect to Postgres (`socket.gaierror: [Errno 11001] getaddrinfo failed`). No secrets were printed.
- QC routing fix validation: focused config/QC flow tests passed (`17 passed, 1 warning`); backend validator passed (`backend-ruff` pass; `backend-pytest` pass; `330 passed, 1 warning in 85.60s`).
- 2026-07-08 final Railway deploy after QC fix: pushed commit `5895f60` and deployed it via Railway upload. Deployment `50aa02be-cb8d-47e7-b22b-18771e118764` reached `SUCCESS`; service status reported `SUCCESS`, `stopped=false`. `/health/ready` returned 200 on fresh instance `1240d2e4-ae4e-48f5-a2d7-d1f343361293`, and `POST /health/image/probe` returned 200 with `grok_imagine_only=ok`, `v3_gcs_upload_only=ok`, and `probe_image_bytes=365926`. Deployment logs showed startup without the production image-store signed-URL warning.
- Completion-audit full local smoke: the first isolated-DB real-provider route smoke proved `generation_complete` with `skeleton_ready`, component stream, two `visual_ready` events, answer key, assembly, review, and a 200 document response. It initially exposed a local smoke misconfiguration: `APP_ENV=development` selected `LocalImageStore`, while `.env` had `IMAGE_BASE_URL` pointing at the GCS public base, producing local files with GCS-shaped URLs that returned 404. Added a cache-hit guard so copied cached visuals are not returned as `ready` unless the destination object exists. Reran the full smoke with `IMAGE_BASE_URL=http://127.0.0.1:8000/images`, Vite on `127.0.0.1:5173`, and a local uvicorn proxy on `127.0.0.1:8000`; result: `generation_complete`, 3 components, 2 `visual_ready` events, both image URLs `HEAD 200 image/png`, PDF export `200` with `X-Page-Count=6` and `601887` bytes, and direct print preflight `response-200` with `images_loaded=2`, `images_failed=0`, `page_count_estimate=6`, `scanned_elements=15`, and 2 oversized-block warnings.
- Cache-copy guard validation/deploy: backend validator passed after the guard (`backend-ruff` pass; `backend-pytest` pass; `331 passed, 1 warning in 53.57s`). Pushed commit `1d4d62f` and deployed it to Railway. Upload command timed out after creating deployment `50c1d773-239f-4a68-92a5-b760adf48921`, but polling showed it progressed through `BUILDING`/`DEPLOYING` to `SUCCESS`; service status reported `SUCCESS`, `stopped=false`. `/health/ready` returned 200 on fresh instance `40d58e12-97ec-47ad-bce9-f29f207bed09`, and `POST /health/image/probe` returned 200 with `grok_imagine_only=ok`, `v3_gcs_upload_only=ok`, and `probe_image_bytes=95841`. Deployment logs showed startup without the production image-store signed-URL warning.
- Final grep checkpoints:
  - `rg "urllib.request.urlopen" backend/src/media/providers/ -n` returned no matches.
  - `rg "_component_order" backend/src/v3_review/ backend/src/v3_execution/ -n` showed section metadata write plus validation stripping.
  - `rg "skeleton_ready" backend/src -n` showed event const plus snapshot hook.
  - `rg "_write_generation_snapshot" backend/src -n` showed the helper and one call site.
  - `rg "omitted_quality" backend/src -n` showed model literal + executor + validation + reviewer.
  - `rg "media_jobs" backend/ -n` returned no matches.
  - `rg '"pages"' frontend/src/lib/builder backend/src/builder -n` returned no matches.
  - `rg "V3_ANSWER_KEY_GENERATOR" backend/src/generation/block_generate.py -n` returned no matches.
  - `rg "img-src" backend/src/app.py -n` returned the CSP rule.
  - `rg "MANUAL_ONLY_COMPONENT_IDS" backend/src -n` returned contract + block generation + reviewer call sites.
  - `rg "svg" backend/src/v3_execution/executors/visual_executor.py -n` returned no matches.

### Phase Notes
- Recent commits suggest Phases 1-3 may already be implemented:
  - `b6cda2b fix(v3): document permanent provider compatibility`
  - `0836141 fix(v3-execution): harden image pipeline diagnostics`
  - `241342d fix(v3): ignore section metadata during validation`
  - `9a3201a fix(v3): persist streaming skeleton documents`
  - `29b4873 fix(v3): paint streaming skeleton canvas`
- Need verify code state and tests before marking those phases done in this runbook.
- Phase 1 verified: repo-root `.env` has `GCS_IMAGE_BASE_URL="https://storage.googleapis.com/lectio-bucket-1"`; Railway production has a non-empty `GCS_IMAGE_BASE_URL` on `storage.googleapis.com`; a read-only production DB scan found no `X-Goog-Signature`, `x-goog-signature`, `X-Goog-Expires`, or `Expires=` markers in recent stored image URL fields. Added the production-like warning for empty `GCS_IMAGE_BASE_URL`.
- Phase 2 completed locally: CSP now includes `img-src 'self' data: https://storage.googleapis.com` plus the configured GCS host, and `create_app()` wires a cached lightweight xAI/GCS probe runner into `/health/image/probe`.
- Phase 3 verified locally: metadata keys are stripped/restored around section validation, `skeleton_ready` is registered/emitted, and one early skeleton snapshot write exists.
- Phase 4 completed locally: OpenAI-compatible and xAI image providers use async `httpx.AsyncClient`; GCS upload path was already wrapped via async/to-thread in the core store; default visual concurrency is now 4.
- Phase 5 completed locally: added `media.qc.visual_qc`, `V3_VISUAL_QC` model node/env overrides, QC accept/retry-once/omit flow in `execute_visual`, `omitted_quality` block status, reviewer minor issue mapping, and frontend type/stream status handling.
- Phase 6 completed locally: added optional `visual_style` (`diagram_precision` or `illustration`) from Stage 2 planner output through blueprint assembly, execution compilation, visual prompt construction, and QC prompt checks. Stage 2 prompt now asks for 2-5 concrete `must_show`/`must_not_show` items and an explicit visual style. Unknown or missing style falls back to illustration behavior.
- Phase 7 completed locally: extracted Playwright print render/scan into reusable preflight path, added measured page-count estimate from rendered scroll height, added `POST /api/v1/builder/lessons/{lesson_id}/print-preflight` with ownership check/rate limit, and surfaced a `Check print` action in the builder toolbar with measured pages, image counts, warnings, and stale-result handling.
- Phase 8 completed locally: added `POST /api/v1/v3/generations/{generation_id}/visuals/{visual_id}/regenerate`, reconstructing the visual work order from the persisted planning artifact, enforcing one in-flight regenerate per generation, applying optional teacher hints, replacing persisted top-level visual blocks, patching rendered section diagram fields, and returning failed/omitted visual blocks as 200 responses when executor output is non-ready.
- Phase 9 completed locally: added `V3_IMAGE_CACHE_ENABLED`, stable prompt/model/mode/must-show hash keys, cache hit copy to per-generation image path, cache miss write-through for QC-accepted images, storage abstraction support for local/GCS exists/copy/key upload, and regenerate cache-read bypass.
- Phase 10 completed locally: added dedicated `V3_BLOCK_WRITER_FAST`/`V3_BLOCK_WRITER_STANDARD` nodes, switched builder AI block generation to those nodes, added explicit `MANUAL_ONLY_COMPONENT_IDS`, rejected manual-only AI-fill requests with 400, and added reviewer major issues for manual-only planned/generated components.

### Closing Summary

| Phase | Status | Notes |
| --- | --- | --- |
| 1 | done | Production `GCS_IMAGE_BASE_URL` set; recent stored packs had no signed URL markers. |
| 2 | done | CSP includes GCS image host; health image probe wired and production probe passes. |
| 3 | done | Internal metadata tolerated, `skeleton_ready` emitted, early skeleton snapshot written. |
| 4 | done | Image clients/storage path non-blocking; production visual concurrency set to 4. |
| 5 | done | QC accept/retry/omit flow wired; QC node now keeps an Anthropic vision default and uses a bounded verdict response. |
| 6 | done | Planner-owned `must_show`, `must_not_show`, and raster visual style carried through prompts/QC. |
| 7 | done-with-discrepancy | Print preflight endpoint and toolbar action added; no existing PDF semaphore was present, so a shared limiter was added. |
| 8 | done | Per-visual regenerate endpoint added with generation-level in-flight guard. |
| 9 | done | Content-hash cache added for QC-accepted visuals. |
| 10 | done-with-discrepancy | Dedicated block-writer slots added; manual-only component guard implemented before registry lookup for clearer 400s. |
| Final | done | Backend/frontend validation green, real-provider image/QC diagnostic passed, Railway backend deployed and production image probe passed. Full local real-provider lesson smoke completed through skeleton/components/visuals/QC, pack completion, export, and print preflight. |

### Commit Message Plan
- `chore(images): verify permanent image URLs in production`
- `fix(health,security): wire image probe and allow GCS images`
- `fix(v3): harden streaming schema and skeleton snapshots`
- `perf(images): use async image clients and raise visual concurrency`
- `feat(images): add vision quality gate for generated visuals`
- `feat(v3): carry visual constraints and raster style through planning`
- `feat(builder): add print preflight checks`
- `feat(images): add per-visual regeneration endpoint`
- `perf(images): cache accepted generated visuals by content hash`
- `fix(builder): use block writer slots and reject manual-only components`

### Risks and Follow-up
- Railway production env inspection/deploy steps depend on available CLI/session access.
- Real-provider validation depends on usable local or production API credentials; never record secrets.
- Railway CLI is not installed in this shell (`railway` command not recognized), but Railway dashboard/browser access was used for the Phase 1 production env and stored-pack checks.
- Railway production update is complete for the backend service: env flags are set, deployment `50c1d773-239f-4a68-92a5-b760adf48921` is healthy, and the production image probe passes.
- Backend full-suite local setup note: if `RUN_MIGRATIONS_ON_STARTUP=false` and the temp SQLite test DB was deleted, create schema with `Base.metadata.create_all()` before running full tests; otherwise runtime-DB tests fail with `no such table: users`.
- Phase 7 path discrepancy: no existing PDF render semaphore/limit was present in `core/pdf_export_runtime.py`; added a shared `pdf_render_semaphore` and used it for both PDF export rendering and print preflight.
- Phase 10 path discrepancy: `image-block`/`video-embed` are present in `lectio-content-contract.json` but not in `component-registry.json`, so the block generation manual-only guard runs before the registry lookup to return a clear manual-only error instead of "unknown component".
- The original handoff recommended one commit per phase, but implementation changes were committed as a single hardening checkpoint because the worktree changes were already interleaved by phase. CI follow-up fixes are being kept in a separate commit.

# Lesson Builder Merge Decisions

## Phase 1 - Move Builder into Textbook Agent frontend

### Decision: Use `lectio-lesson builder` as migration source
- **Context:** The unified guide's Phase 1 FROM/TO map references builder folders inside `lectio`, but the current `lectio` repo no longer has those builder routes/components.
- **Guide says:** Move builder code into textbook agent frontend and keep Lectio as package-only contract/render layer.
- **Chose:** Use `C:\Projects\lectio-lesson builder` as the authoritative source for the existing builder implementation, then adapt imports and integration to textbook agent conventions.
- **Risk:** Some source paths or assumptions may differ from the older structure referenced by the guide; integration checks in textbook agent are required to catch drift.
### Decision: Allow adapter bridge to import V3 converter + generation exporter
- **Context:** Phase 1 import rule says builder should avoid imports from `$lib/studio/*` and `$lib/generation/*`, but the phase task explicitly requires composing `adaptV3PackToLectioDocument()` and `exportToLessonDocument()`.
- **Guide says:** Create `src/lib/builder/adapters/from-generation.ts` using those two functions.
- **Chose:** Implemented this bridge only in `src/lib/builder/adapters/from-generation.ts` and kept all other builder files free from direct studio/brief imports.
- **Risk:** This adapter is a controlled coupling point and should remain the only exception; additional cross-imports would violate builder isolation.

### Decision: Use local-install validation flow for unpublished `lectio@0.4.5`
- **Context:** Frontend dependency target is `lectio@0.4.5`, but npm registry does not yet provide that version in this workspace flow.
- **Guide says:** Frontend must align to the new Lectio version and pass `check` + `build`.
- **Chose:** Kept `frontend/package.json` pinned to `0.4.5` and validated by installing local `../../lectio` plus running full frontend checks/build/tests.
- **Risk:** CI or fresh installs without local publish may need explicit local/registry coordination until `0.4.5` is published.

## Phase 2 - Backend Persistence

### Decision: Use server-authoritative lesson IDs and normalize document IDs to server UUID
- **Context:** Phase 1 created purely client-side lesson IDs in IndexedDB. Phase 2 requires server ownership and persistence as source of truth.
- **Guide says:** "POST /builder/lessons -> save to IDB -> navigate" and use server-assigned UUID.
- **Chose:** Backend `POST /api/v1/builder/lessons` always generates the canonical lesson UUID and rewrites `document.id` to match it before persistence/response.
- **Risk:** Older local-only IDB lessons from Phase 1 can exist with non-server IDs and will need migration/recreate flows if reopened.

### Decision: Validate hard integrity only on save; keep pedagogy out of backend blocking rules
- **Context:** Builder is teacher-owned and should not be blocked by pedagogical heuristics, but malformed documents must not be persisted.
- **Guide says:** Block only hard integrity failures (shape, unknown component, bad block refs, payload limits, auth/ownership).
- **Chose:** Added hard validation in backend builder routes for required LessonDocument shape, known `component_id`, section->block reference integrity, and payload size limits.
- **Risk:** Some non-critical content inconsistencies remain possible by design and should surface as UX warnings rather than server rejections.

### Decision: Reuse existing sync-queue primitives with a new builder server-sync adapter
- **Context:** Existing builder persistence already had IndexedDB and a sync queue abstraction, but no server CRUD integration.
- **Guide says:** Keep IDB as offline cache while server remains authoritative; reconnect should sync queued work.
- **Chose:** Implemented `server-sync.ts` to debounce server PUTs, enqueue retryable failures, and register a queue adapter flushed on reconnect/manual save.
- **Risk:** Toolbar save status reflects immediate save attempts; background queue flush success may not instantly update status until next save cycle.

## Phase 3 - Palette, Block Management, and Canvas Polish

### Decision: Replace permanent sidebar palette with centered overlay workflow
- **Context:** Existing builder UI used a permanently mounted `PaletteSidebar` and drag-in palette stubs.
- **Guide says:** Palette should be a centered overlay opened by an "Add block" action, with grouped search and click-to-insert behavior.
- **Chose:** Added `PaletteOverlay` and routed AppShell through a server-friendly click-to-insert flow: open overlay -> choose block -> `store.addBlock()` -> select/edit new block -> close overlay.
- **Risk:** Dragging from palette into canvas is no longer the primary insertion path; composition is now button-driven for consistency and clarity.

### Decision: Ship group-based palette mapping until exported Lectio intent groups are available in this workspace package
- **Context:** The guide references `PALETTE_GROUPS` from Lectio Phase 0b. In this workspace, the installed `lectio@0.4.5` export surface does not currently expose `PALETTE_GROUPS`.
- **Guide says:** Group by teaching intent using Lectio-owned grouping metadata.
- **Chose:** Implemented grouped palette metadata via `getComponentsByGroup()` with intent-aligned labels/colors as a compatibility bridge, and documented the export mismatch as follow-up.
- **Risk:** Strict interpretation of "must use `PALETTE_GROUPS`" remains partially blocked until the frontend consumes a Lectio build exporting those symbols.

### Decision: Convert outline panel to compact dot rail while keeping section reordering support
- **Context:** Existing outline was a full-width panel with row links and visible drag handles.
- **Guide says:** Replace it with a narrow dot rail with active highlight and quick navigation.
- **Chose:** Reworked `CanvasOutline` to a 44px-style dot rail with section hover titles and active state, while retaining `dragHandleZone` reorder behavior behind the compact UI.
- **Risk:** Compact controls reduce discoverability for section drag-reorder; may need onboarding hint copy in polish phase.

## Phase 4 - Block Editing and AI Assist Hardening

### Decision: Bind block generation to editable lesson ownership when lesson_id is present
- **Context:** Block AI generation endpoint accepted authenticated calls but did not verify lesson ownership when used from the builder.
- **Guide says:** Builder AI requests should be teacher-owned and scoped to editable lessons.
- **Chose:** Extended `/api/v1/blocks/generate` request handling to accept `lesson_id` and verify `(lesson.id, lesson.user_id)` against the current user before generation.
- **Risk:** Legacy callers that omit `lesson_id` still bypass this ownership check by design; follow-up tightening may require phased rollout.

### Decision: Preserve hidden/internal block fields during AI apply via schema-aware merge
- **Context:** AI responses could overwrite fields that are not intended to be teacher-editable.
- **Guide says:** AI can only write fields exposed by `getEditSchema()`; hidden/advanced fields should not be overwritten.
- **Chose:** Added `mergeAiContentWithEditableFields(...)` in the builder to apply generated values only for non-hidden schema fields, preserving existing hidden/internal content and ignoring unknown keys.
- **Risk:** Enforcement currently lives in frontend apply logic; server-side parity should be added when backend has direct access to the same edit-schema surface.

## Phase 5 - Shared Media Manager and Uploads

### Decision: Reuse `GCSImageStore` with explicit object keys for builder-owned media
- **Context:** Builder needed lesson-owned media uploads with a new GCS prefix, but the existing storage service only exposed generation/section-oriented keys.
- **Guide says:** Reuse existing GCS infrastructure and upload under `editable-lessons/{lesson_id}/media/...`.
- **Chose:** Extended `GCSImageStore` with `upload_with_key(...)`, then used it from builder media upload route to avoid introducing parallel storage code paths.
- **Risk:** In environments without configured GCS (`GCS_BUCKET_NAME`/credentials), uploads are unavailable and the API returns `503`.

### Decision: Move image handling from data-URI persistence to server-uploaded URLs
- **Context:** Existing builder media flows stored uploaded images as inline data URIs in lesson JSON, which does not satisfy server-owned persistence and cross-device durability expectations.
- **Guide says:** Media uploads should go through backend ownership checks and stored URLs.
- **Chose:** Added `frontend/src/lib/builder/api/media-upload.ts` and updated `ImageUploader`/media field integrations to upload files first, then store returned URL references in the lesson media map.
- **Risk:** Current `lectio` `MediaReference` type in this workspace does not include a `source` field, so source metadata could not be recorded without contract changes.

## Phase 6 - Manual Lesson Creation and Listing

### Decision: Keep `/builder/new` as the single creation surface and add `/builder` as the resume/listing surface
- **Context:** Manual creation flow already existed and created server-backed lessons, but there was no dedicated builder index route to list editable lessons.
- **Guide says:** Provide `/builder/new` for manual creation and a builder index page listing user lessons.
- **Chose:** Kept existing `/builder/new` logic and added `frontend/src/routes/builder/+page.svelte` for listing/resume, instead of splitting creation into multiple new screens.
- **Risk:** Listing is currently unpaginated; large lesson collections may need filtering/pagination in a later phase.

### Decision: Add explicit Builder entry points in both global nav and dashboard
- **Context:** Teachers could reach builder routes via direct URLs but lacked obvious navigation affordances.
- **Guide says:** Include "New Lesson" entry point in nav or dashboard and expose builder list flow.
- **Chose:** Added `Builder` and `New Lesson` links to the global authenticated nav and a dedicated Lesson Builder card in dashboard.
- **Risk:** Additional nav items increase top-bar density on smaller screens; future mobile polish may consolidate actions.

## Phase 7 - Version History and Print/Export

### Decision: Reuse the existing PDF pipeline with a builder-specific print route instead of adding a new renderer
- **Context:** Backend PDF export already uses Playwright + `export_generation_pdf(...)` with optional custom render paths, but builder lessons did not have a dedicated print endpoint/route.
- **Guide says:** Add builder teacher/student PDF export while reusing existing PDF infrastructure.
- **Chose:** Added:
  - backend `GET /api/v1/builder/lessons/{id}/print-document?audience=...`
  - frontend `/builder/print/[id]` route with print readiness attributes for Playwright
  - backend `POST /api/v1/builder/lessons/{id}/export/pdf` that calls `export_generation_pdf(...)` using `render_path=/builder/print/{id}?audience=...`
- **Risk:** Builder export now depends on frontend print route compatibility (`data-generation-complete` contract) just like studio export; route regressions could affect PDF capture reliability.

### Decision: Enforce student-copy answer stripping in backend print payload, not in frontend
- **Context:** Audience behavior is security/ownership-sensitive and must not rely on frontend-only logic.
- **Guide says:** Student export strips/hides answer fields; teacher export includes answers.
- **Chose:** Implemented backend answer stripping against a copied lesson payload for student audience on:
  - `quiz-check` (`options[].correct`, `options[].explanation`, feedback fields)
  - `short-answer` (`mark_scheme`)
  - `practice-stack` (`problems[].solution`)
  - `fill-in-blank` (`segments[].answer`)
  while leaving persisted lesson data unchanged.
- **Risk:** If new answer-bearing components are introduced, this stripping map must be extended to preserve student-copy expectations.

### Decision: Use content-rendered audience mode and disable appended answer-key pages for builder PDF export
- **Context:** Existing PDF pipeline can append answer-key pages from pipeline section structures, but builder export is sourced from lesson render route with audience transformations.
- **Guide says:** Teacher copy includes answers, student copy strips answers, both via shared export pipeline.
- **Chose:** Set builder export request to `include_answers=false` and rely on audience-specific rendered content (`teacher` includes, `student` strips) to avoid mismatch between rendered body and appended answer key pages.
- **Risk:** If product later expects a separate teacher answer-key appendix for builder lessons, endpoint contract and UI options will need explicit expansion.

## Phase 8 - Polish and Production Hardening

### Decision: Keep save reliability UX local to the toolbar with explicit retry hook
- **Context:** The guide requires visible save error handling with retry while preserving teacher edits.
- **Guide says:** Save state should show saving/saved/error with retry.
- **Chose:** Added `onRetrySave` to `DocumentToolbar` and wired `AppShell` retry to `store.flushSave()`, without introducing a second persistence path.
- **Risk:** Retry action currently triggers queue flush only; if repeated backend failures occur, teachers still need clearer long-form diagnostics in a future pass.

### Decision: Enforce route-level 401/404 handling directly in `/builder/[id]`
- **Context:** Prior behavior used generic loader errors and did not provide clear lesson-not-found or auth-expired UX.
- **Guide says:** Unauthorized should redirect to login; not-found should render an appropriate error state.
- **Chose:** Added explicit `isApiError` branching in `+page.svelte`: `401` triggers `logout()` + redirect, `404` renders a local "Lesson not found" state, and other failures render a generic load error panel.
- **Risk:** This is page-local handling; shared builder route error primitives may still be useful if more route-level error states are added later.

### Decision: Add backend request-scoped structured logs and save endpoint throttling in existing builder routes
- **Context:** Production hardening requires operational visibility and protection from rapid-fire save storms.
- **Guide says:** Add structured builder logs and rate limiting on save endpoint.
- **Chose:** Added `_log_builder_event(...)` with request metadata (`request_id`, method, path, lesson/user IDs) across CRUD/upload/print/export and applied `@limiter.limit("120/minute")` on lesson `PUT`.
- **Risk:** Current limit is static and environment-agnostic; high-throughput classroom scenarios may need configurable thresholds.

### Decision: Align frontend Lectio dependency to published `0.4.6` for success-criteria verification
- **Context:** This worktree still pinned `lectio@0.4.5`, while registry/package availability and the primary repo had moved to `0.4.6`.
- **Guide says:** There should be exactly one Lectio version in the dependency tree.
- **Chose:** Updated `frontend/package.json` to `lectio@0.4.6` and verified `npm ls lectio` resolves to a single installed version.
- **Risk:** If another branch still pins `0.4.5`, merges may need a lockfile reconciliation pass.

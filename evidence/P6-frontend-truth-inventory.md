# P6 — Frontend state truth inventory and proposal

Status: Read-only inventory complete; awaiting Sol design review. No P6 product code has been changed.

## Canonical backend contract

`GET /api/v1/units/{unit}/path/lessons/{lesson}/status` already returns `workspace` plus deprecated raw `generation_status`/`workflow_stage` fields and an explicit `worker_debug` object. The canonical preparation states are `not_started`, `planning`, `awaiting_review`, `approved`, `failed_recoverable`, and `failed_terminal`; `awaiting_review` carries `review_kind` (`structural` or `teaching_plan`). The Learn and Print projections independently return `not_created`, `queued`, `running`, `ready`, `failed_recoverable`, or `failed_terminal`, with path identity, open link, stale/ambiguous flags, and typed error details. Error metadata includes code, type, failure class, message, retryability, stage, work item, attempt, and recovery action.

Backend retry/recovery meaning:

- Artifact retry is valid only for `failed_recoverable` with `error.retryable === true`; retry targets the exact `realization_id`.
- `failed_terminal` is not a retry invitation. `recovery_action: reprepare` or `review_teaching_plan` returns the teacher to Plan; other explicit actions such as `reload_lesson` should be represented directly.
- `stale` is projected as terminal with `REALIZATION_STALE` and `recovery_action: reprepare`; it must not be mapped to retryable from a raw realization row.
- `legacy_ambiguous` means the UI must not infer path identity from a nearby output, worker stage, or another path. Verified `ready` paths retain their canonical output link.
- Preparation `approved` remains approved through Learn/Print failures. `stale: true` still blocks new realization admission and offers the backend-authorized reprepare action.

## Active UI inventory

| Surface | Current state source | Mismatch or risk |
| --- | --- | --- |
| `src/lib/curriculum/lessons/lesson-context.ts` | `preparationUiState` infers status from deprecated `workflow_stage`/`generation_status` substrings and output presence. `lessonArtifactUi` uses canonical workspace when present, but falls back to realization rows, IDs, output pointers, and guessed readiness. It also derives retryability from a legacy row when canonical error metadata is absent. | Canonical preparation states and review kind are discarded. A stale worker stage or output pointer can label preparation/artifact ready. Terminal/stale artifacts can be treated as retriable by fallback. |
| `src/routes/units/[id]/lessons/[lessonId]/+layout.svelte` | Header badges call the helper above. Refresh fetches canonical status but swallows failures without clearing or surfacing stale status. | Every lesson tab inherits the guessed preparation badge. Failed refresh can leave old truth displayed without a visible status-load error. |
| `src/routes/units/[id]/lessons/[lessonId]/plan/+page.svelte` and `src/lib/curriculum/lessons/plan-status.ts` | The UI fetches `getChunkedPlanStatus()` directly, derives phase from worker-stage strings, stage substring checks, local `phase`, and a separate Teaching Plan review fetch. `isPlanGenerationFailure`/`failureAllowsRetry` use raw stage/error detail. Artifact cards use workspace-preferred helper but offer Retry whenever a realization ID exists; the retry handler does not verify canonical retryability. | `workspace.preparation` is not the phase authority; review kind and canonical error/recovery action are unused. Raw worker state can contradict verified approval or awaiting review. Retry can call the backend for stale/terminal rows. |
| `src/routes/units/[id]/lessons/[lessonId]/learn/+page.svelte` | Artifact display is routed through `lessonArtifactUi`, then Learn document/open-builder APIs. It refreshes the canonical path status and uses serialized polling. | The canonical path is mostly in place, but helper fallback can override it when present but incomplete; Create is shown for `not_created` without checking `workspace.preparation` is verified/fresh `approved`. Builder/open href can fall back to non-workspace path fields. Error `recovery_action` is ignored. |
| `src/routes/units/[id]/lessons/[lessonId]/print/+page.svelte` | Display uses `lessonArtifactUi`, but `printIsActive()` independently checks preparation worker stage and realization row status. The view separately fetches output document by resolved output ID. Retry-preview calls retry without checking `artifact.retryable`. | A stale/failed canonical artifact can keep polling because an old worker stage says active. Output load failure is conflated with realization retry, so a ready artifact may show a retry action that the backend will reject. Create is not gated on canonical approved/fresh preparation. |
| `src/routes/units/[id]/+page.svelte` | Lesson card labels call `preparationUiState`; fresh-start and regeneration use `workflow_stage` plus generation status, and `prepare()` chooses reuse/reprepare from generation ID and raw stage. | Worker status is duplicated as policy. Contradictory canonical review/approval can cause the dashboard to route to Learn/Print admission instead of Plan review or vice versa. It does not use canonical error recovery action. |
| `src/routes/studio/+page.svelte` | Legacy Studio navigation and poller intentionally consume generation/chunked stages (`stage2_running`, `planning_forms`, `writing_sections`, `awaiting_teaching_approval`, etc.) to select editor panes, streams, and resume actions. | No path-lesson identity is available in `V3GenerationDetail`/Studio DTO to fetch the canonical Unit workspace projection. Keep detailed worker progress for this generation editor; do not present it as the canonical Unit Plan/Learn/Print badge. A broader Studio lifecycle migration would need an API linkage contract. |
| `src/routes/studio/generations/[id]/+page.svelte` and `src/routes/studio/print/[id]/+page.svelte` | Generation-level `detail.status`, document presence, and visual-quality retryability control document rendering/export. | These routes render a specific output and must retain output/document readiness checks. They are not a replacement for path-level realization state; any P6 changes should preserve old ready-output reads and visual retry behavior. |

The lesson status API is already fetched by the shared Unit lesson layout and unit overview. No backend status projection change is needed for those surfaces. The Studio pages do not have a PathLesson identifier in the current generation-detail DTO, so applying Unit workspace state there is not a safe frontend-only lookup.

## Bounded P6 proposal

1. Add precise TypeScript interfaces for preparation/workspace/error DTOs, including `review_kind`, approval identity verification, `legacy_ambiguous`, and debug-only worker fields. Mark top-level `generation_status`/`workflow_stage` deprecated compatibility data in the frontend type.
2. Make `lesson-context.ts` map canonical workspace states directly. When `workspace` exists, never reconstruct an alternate state or identity from the raw worker fields or other path. Model legacy/ambiguous data explicitly. Expose canonical state, stale/ambiguous flag, output identity, error, and recovery action without dropping `failed_recoverable` versus `failed_terminal`.
3. Use preparation projection for Unit overview badges, Start/Prepare routing, lesson header badges, and Plan screen phase. Keep worker detail endpoints only for structural-plan payload/progress rendering; `workspace.preparation.review_kind` chooses structural review versus Teaching Plan review, and canonical approved/failure states win over contradictory worker stages.
4. Use path artifact projection for Learn/Print Create, poll, ready, failure, and retry decisions. Create only when preparation is verified `approved` and fresh. Retry only when the selected path state is `failed_recoverable` and its typed error is retryable. `recovery_action` controls navigation/reprepare guidance. Distinguish a document-fetch/preview error from a failed realization, so document refresh does not call realization retry.
5. Keep Studio's detailed editor stage machine and direct output visual/document checks for now; document the separation in code only if needed. If Sol wants canonical path state in Studio, add a backend path/output lookup contract as a separate design decision before implementation.

## P6 acceptance matrix

- Unit-test canonical preparation and artifact state mappings for every allowed state, with deliberately contradictory raw worker stages and stale output pointers.
- Prove approved preparation stays approved while either artifact fails; structural versus Teaching Plan review uses `review_kind`; a failure cannot become ready because an output ID exists.
- Prove path independence, output identity/open links, and `legacy_ambiguous` behavior: no guessed output, retry, or cross-path identity.
- Prove retry only appears/calls for retryable `failed_recoverable`; stale and terminal errors surface their typed message and reprepare/review action. A document-preview read failure does not retry a ready generation.
- Plan component tests cover `planning → awaiting_review → approved`, failed preparation, refresh after approval/reprepare, and contradictory worker-stage responses.
- Add Learn/Print component tests (none currently exist at the Unit lesson page paths) for `not_created → queued → running → ready`, recoverable retry, terminal/stale handling, and refresh/resume using the canonical output ID.
- Unit overview tests cover canonical badge and operation routing despite legacy status fields disagreeing.
- Preserve existing Studio integration tests for editor stage resume and detached Print output refresh; verify P6 does not change pathless Studio behavior.

No P6 product code has been modified. Sol review is needed on the Unit-workspace versus generation-editor boundary before edits begin.

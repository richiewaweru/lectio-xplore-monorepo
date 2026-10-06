# 35 — Media Fix: Working Figures, One Decision Authority, Truthful Status

Status: APPROVED DIRECTION (rev 4, 2026-10-05) — hand to Claude Code as the work order
Repo: `richiewaweru/lectio-xplore-monorepo`, app `apps/textbook-agent`
Related: `34_DEMO_SLICE_AMENDMENT.md` (B5 figures; this doc supersedes B5's required/supporting split for the stand-in phase)

Rev 4: settled how text and image stay consistent. The plan's `visual` spec is a contract that both the writer and the image request obey; the image is still generated after the section text, from the spec plus the writer's wording; a cheap code check catches drift (section 1.2, C3, C4).
Rev 3: the structural plan carries no visual decision; the deterministic `visual_required` flag is deleted end to end; the reasoning teaching plan alone decides.
Rev 2: where visuals are decided today; composer no longer decides figures; explicit cut list; keys live in `.env`, not `.env.example`.

## 0. Goal (the only thing this work must achieve)

1. **Figures work and show up.** A Print run that plans figures generates them via Gemini and the booklet contains them.
2. **Errors are truthful.** When anything fails (figure, section, timeout), the status says what failed, whether it is retryable, and what to do. Nothing says "queued/ready/working" when it is not.
3. **Media planning and execution are one chain.** One component decides whether a figure exists and what it must show; everything downstream obeys it and never invents.
4. **Image and text agree.** The figure must not look out of place against the section text and caption (observed before: images inconsistent with the text even when fed the right brief).

**Not a goal:** media quality. Let everything pass. QC stays off or advisory. Do not tune prompts for beauty.

Principle: one source of authority for decisions; it flows downstream; downstream never invents. Gemini image generation is the only media type for now (it stands in for charts/diagrams/SVG; Gemini draws its own labels). Keep the interface clean (work order in, result + truthful status out) so a separate media service can replace it later, but do not build that now.

## 1. The settled design

### 1.1 Where visuals are decided today, and who owns it

Visuals are touched in four places today. That is the divergence.

| Stage | What it does today | Verdict |
|---|---|---|
| **Structural plan** (fast; `curriculum/planning/skeletons.py`) | Sets `visual_required` on `explain`/`model`/`organise` slots when `objective_is_spatial_or_process()` matches the objective text (regex). | **Remove** the flag and everything carrying it (cut list 6). It only picks slots. |
| **Teaching plan** (long call; `resources/lesson-approach-planner-v2.txt`) | Receives the flag; describes labels/stages only in the free-text `brief`. | **Sole owner.** It reasons over objective, `must_establish` and sourcebook. Gets a structured `visual` field (below). |
| **Section composer** (`document/shared_lesson/composer.py`, `section-composer.md`) | Re-decides by substring cues (`visual, diagram, figure, show, model, structure, part, flow, map, image`) then LLM picks kind=figure. | **Remove** (cut list 1–2). Code places figures. |
| **Section writer + media** (`document/shared_lesson/media.py` ~L390) | Writer writes caption/alt; image work order is built only from them (`purpose = caption or alt`, `must_show = [alt]`). Plan labels and `stimulus_dependencies` unused. | **Change** (C3). Writer and image both obey the plan spec. |

New structured field on `TeachingPlanBlock` (and its draft twin at ~L58 and ~L276 in `curriculum/teaching_plan/models.py`; reuse names from `media/generation/contracts.py::VisualPlanItem`):

```text
visual: null | {
  mode:            "diagram" | "chart" | "illustration" | ...   # reuse VisualMode
  purpose:         short sentence — what the learner must notice
  must_show:       [str]     # exact stages/parts/relationships, from objective/must_establish only
  labels_required: [str]     # exact label text the figure must carry
  must_not_show:   [str]
  required:        bool      # true => run is not complete without it
}
```

Rules:
- The plan decides, by reasoning, whether any block needs a `visual`. No input flag, no keyword rule. Default is none. Never add a deterministic "objective mentions X therefore a figure" check.
- Code validates only the *shape*: non-empty `purpose` and `must_show`; `labels_required` drawn from `must_show`, the objective or `must_establish`. Optional: one advisory line in the existing semantic reviewer (`medium`): "if the objective names a diagram, labelled figure or process picture and the plan has no `visual`, raise an advisory issue" (model judgement, not a regex).
- `visual` is part of the approved plan and its content hash. Plan review shows "Figure planned: <purpose>".
- Rewrite the planner prompt's VISUAL REQUIREMENTS section (`lesson-approach-planner-v2.txt` ~L63–86); delete the `visual_required` / `required_visual_slots` input lines (~L32–33). New text: you decide whether the lesson needs a visual from the objective and `must_establish`; when it does, fill the block's `visual` object (exact labels/stages only, never invented); a visual is never decorative and never replaces the explanation. Keep the rest of the planner prompt. The planner stays one call.

### 1.2 Consistency design (text and image agree)

Cause of past mismatches: text and image were produced from two separate descriptions. Earlier fix (image after text, from the writer's caption) worked but made the writer a second decision-maker. Settled approach: **sequential, with the plan spec as the contract for both.**

Flow per figure:
1. **Plan** (DeepSeek) decides the `visual` spec. Only decision point.
2. **Code** records an "expected" figure per planned `visual` and places one `figure` node at that block's position (identity from the plan block id). Composer cannot add/move/remove.
3. **Writer** (DeepSeek section writer) is given the spec for that block: it must use the exact `labels_required` / `must_show` wording in the prose and write the figure **caption** under that spec. It may not rename, add or drop anything. It does not write alt text.
4. **Code check, no model** (after the section is written, before the image): every `labels_required` entry appears in the section text or caption (case-insensitive, whitespace-normalised). A miss is recorded as a warning on the figure record (`label_missing:<label>`), visible in status/logs, and **does not block** (quality passes everything). It tells us which side drifts.
5. **Media** builds the image request from a fixed code template: plan spec is authoritative (`purpose`, `must_show`, `labels_required`, `must_not_show`, `mode`); context appended: the writer's caption and the one or two sentences that refer to the figure (so terminology matches the section). No LLM rewrites the prompt.
6. **Gemini** draws the image (labels included). Media also produces the **alt text**: capture the Gemini text part from the same call if present (the client already requests `TEXT` + `IMAGE` but currently discards text; keep it); if absent, build alt from `purpose` + `must_show` + `labels_required` in code.
7. **Bind and assemble.** Image, caption (writer) and alt (media) bind to the node. Document hash is computed only after every figure has settled.

Authority summary: the plan decides *what must exist and show*; the writer and the image both obey that; the media step owns the image and alt text; nothing downstream invents.

Pending state: a figure node exists with no asset and no alt until media settles. The existing "figure requires meaningful alt text" check (`document/shared_lesson/media.py`) must accept a `pending` node and enforce alt only at READY. Teacher preview shows "Figure planned" until then.

Deferred, not now: starting figure generation in parallel with the writer for speed. Revisit only after consistency is proven.

## 2. Scope of changes

### A. Truthful status and errors (highest priority)

A1. **Figure failure must fail the run visibly.** Observed: figure step failed (5/5 xAI 403) while the realization stayed `queued`, with no error text and no recovery action. A failed required media work item must make the run `failed_recoverable` with a per-figure record: `figure_id`, `section`, `status`, safe `error_code`, sanitized `provider_status` (`provider_http_403`, `provider_timeout`, `provider_no_image`), `warnings` (e.g. `label_missing:...`), `retryable`, and a `recovery_action` (retry figures). Media failures currently collapse into generic codes; keep a specific safe code. Details stay in logs/`LLMCallFailedEvent`, never in teacher-facing text.
Look at: `document/shared_lesson/media_runtime.py` (`media_readiness`, `failed_required_work_item_ids`), `media.py` (~L810–830), `worker.py` (~L291 blocked outcome, ~L700 `_terminalize_blocked_post_section`), `application/unit_lesson/realization_projection.py::project_realization_status`, `curriculum/lesson_progress.py::project_artifact_progress`.

A2. **Expected vs generated is visible.** At plan approval one record per planned `visual` exists. Progress shows `Figures: 2 ready / 1 failed / 5 planned`, never a bare counter stuck at 0/5.

A3. **Timer bug (naive datetime).** "184m 08s" came from naive/local vs UTC `started_at` (`lesson_progress.py` ~L161, fed by `curriculum/routes.py` ~L376 `shared_started_at`). Make everything timezone-aware UTC; test that a just-started run shows under a minute.

A4. **No false "ready".** `visual_quality` reports `unreviewed` when QC is off.

A5. **Retry works for media.** `POST …/realizations/{id}:retry` (`curriculum/routes.py` ~L1659, `application/unit_lesson/realization_retry.py`) retries only failed figure work items; plan, sourcebook and finished sections untouched. Test it.

### B. Section-writer DB rollback bug

Logs showed `InFailedSQLTransactionError` after a section failure, then ~5 minutes waiting for the lease to expire (the "stuck on section" symptom). The failure handler only rolls back if the lease checkpoint committed or `session.is_active is False`, so raw DB errors before the claim commit are missed. Fix: always `await session.rollback()` before `_record_execution_failure` (start in `document/shared_lesson/runtime.py` / `worker.py`). Also trace the `MissingGreenlet` seen on pool ping. Regression test: inject a DB error mid-section; failure is recorded and retryable within seconds.

### C. One authority, enforced in code

C1. Add the `visual` field and its shape validation (section 1.1).
C2. **Figures are placed by code, not chosen by the composer.** For every plan block with `visual != null`, code inserts exactly one `figure` node in that block's section at that block's position. The composer's output vocabulary drops `figure`. Tests: composer output containing a figure is rejected; plan with N visuals → document with exactly N figure nodes.
C3. **Writer bound to the spec; image request from spec plus text.** Writer prompt (`resources/prompts/shared-section-writer.md`, `figure-authoring.md`) receives the block's `visual` spec, must use its exact labels/wording, writes the caption only, never alt, never adds/renames/drops a figure. `media.py` (~L390) and `media_runtime.py` (~L311) build `VisualPlanItem` from the plan spec (`purpose`, `must_show`, `labels_required`, `must_not_show`, `mode`, `attaches_to` the code-placed node) with writer caption and referring sentences appended as context. Honour `stimulus_dependencies` where a block lists an asset id; otherwise leave unused.
C4. **Label-consistency check** (step 4 of the flow): deterministic, non-blocking, recorded as figure warnings. Unit tests for exact, case, whitespace and missing-label cases.
C5. No `visual_required` flag exists anywhere upstream of the plan (cut list 6).

### D. Failure policy for this phase

Failed figure → run `failed_recoverable` with the specific error and a Retry action (A1/A5). No placeholder text, no provider errors inside captions. Do not rely on `SHARED_DOCUMENT_MEDIA_OPTIONAL` (rejected in `production`/`staging`, `infra/config.py::_PRODUCTION_LIKE_ENVS`); see cut list.

### E. Quality passes everything

`V3_VISUAL_QC_ENABLED` off (or advisory, never blocking). `ready_with_quality_warning` is acceptable; blocking on quality is not. Skip the `diagram_precision` label compositor (`media/diagram_compositor.py`, called from `media/generation/executor.py`) when `IMAGE_PROVIDER=gemini`; Gemini draws its own labels.

### F. Gemini wiring (done on branch `gemini-image-config`, pushed)

Env vars: `GEMINI_IMAGE_API_KEY`, `GEMINI_IMAGE_MODEL` (default `gemini-3.1-flash-lite-image`), `GEMINI_IMAGE_THINKING_LEVEL` (`minimal`/`high`). Registry ignores the generic `IMAGE_MODEL_NAME`/`IMAGE_BASE_URL`/`IMAGE_API_KEY_ENV` for Gemini. To do: (1) one real call to confirm the lite model id works through `generate_content_stream`; if rejected, default to `gemini-3.1-flash-image` and note it; (2) capture the text part of the response in `media/providers/gemini_image_client.py` (extend `ImageGenerationResult` with optional `text`) for alt text (flow step 6). Storage (GCS/local) is known good; do not change it.

## 3. Cut list (delete, do not leave dormant)

Goal: one working path. Remove these, with tests that referenced them, once the replacement passes.

1. **Composer figure logic** (`document/shared_lesson/composer.py`): `"figure"` from `_KIND_CUES`, the figure entry in the kind→role table, `visual_model`/`visual_interpretation` as composer-chosen roles, and figure handling in `_eligible_non_paragraph_kinds` and `_paragraph_run_guidance`. Figure nodes may still exist, but only code-inserted ones (C2).
2. **Composer prompt** (`resources/prompts/section-composer.md`): remove `figure` from "ordinary kinds", its cue list (~L23–24), the figure role rules (~L42) and figure mentions in the paragraph-run guidance (~L57). Add one line: figures are placed by code and must not be emitted.
3. **Writer-authored figure decisions**: remove any instruction in `shared-section-writer.md` / `figure-authoring.md` that lets the writer request, add, rename or drop a figure, and remove writer-authored alt text. The writer keeps only: prose that obeys the spec, plus the caption (C3). Keep the prompt names registered in `core/prompts/loader.py` (~L88).
4. **Caption/alt-only work order**: the `purpose=caption/alt, must_show=[alt]` construction in `media.py` (~L390) and the equivalent in `media_runtime.py` (~L311), replaced by C3.
5. **Local-only optional-media branches**: the `media_optional` / `shared_document_media_optional` paths in `media.py` (~L724–775) and `media_runtime.py` (~L542–584), the config flag in `infra/config.py`, and its production-like-env rejection check. They are a second, untruthful way to finish a run.
6. **The deterministic `visual_required` flag, end to end**:
   - `curriculum/planning/skeletons.py`: `objective_is_spatial_or_process`, `_SPATIAL_VISUAL_SLOT_IDS`, `_visual_slots_for_objective`, the `visual.spatial_objective` toggle and diff entry (~L311–333), `SkeletonSlotPreview.visual_required`.
   - `resources/skeletons.yaml` (~L433–437): the `visual.spatial_objective` toggle with `flag: visual_required`.
   - `application/unit_lesson/prepare.py` (~L235–290, L414, L560–594, L641–662) and `application/unit_lesson/teaching_plan_service.py` (~L138–178): the `visual_required_by_slot/instance/role` plumbing and `required_visual_slots` in the planner payload.
   - `print/generation/whole_lesson/packet.py` (~L65, L112–124), `packet_builder.py` (~L61–86), `validation.py` (~L499), `curriculum/flow_validation.py` (~L22–41), `curriculum/teaching_plan/projections.py` (~L70): the slot field and the check that a flagged slot has a visual block. Replace with: every block carrying a `visual` is well-formed.
   - `curriculum/lesson_review/issue_projection.py` (~L218–272): the "section marked visual_required has no figure" issue. Rebase on plan `visual` objects: a planned visual with no figure, or a failed figure, is the issue.
   - Frontend: the "Visual required / No visual required" label in `StructuralPlanPreview.svelte` (~L32), `visual_required` in `lib/types/units.ts` (~L374), the `LessonShapePanel.test.ts` fixture. Plan review shows "Figure planned: <purpose>" instead.
   - Tests that encode the flag (`tests/planning/test_packet_slot_derivation.py`, `test_teaching_validation.py`, `test_prompt_resources.py` L46–48, `test_path_bridge.py`, `test_lesson_issue_projection.py`): rewrite around plan `visual`.
   Scope note: `visual_required` also exists on the older V3 blueprint / structural-planner path (`v3_blueprint/models.py`, `curriculum/models.py` ~L655, `resources/prompts/structural-planner.md`, `section-expander.md`, `print/http/v3_studio/*`). There the model reasons about it and echoes it, so it is not the deterministic check. Determine which are still on the live Print path. If only on the legacy V3 studio path, leave and list in the PR; if the live path reads it, remove or rebase as above.
7. **Compositor on the Gemini path** and **QC as a gate** (E): remove the call-site coupling; leave the modules for the later media service.
8. **Dead statuses**: any `visual_quality: ready` default when QC did not run (A4).

Do **not** delete: provider registry (xai/openai stay selectable), `media/storage/*`, `media_dispatcher.py` (restart-safe orchestration), image store, the `VisualPlanItem` contract.

## 4. Local test procedure (Claude Code does this itself)

Follow `AGENTS.md` and `docs/project/SETUP.md`.

1. DB: `docker compose --profile dev up db-dev`.
2. Config: the owner has put the real keys in **`.env`** (not `.env.example`). Use that file as is: `IMAGE_PROVIDER=gemini` and `GEMINI_IMAGE_API_KEY`. Do **not** copy secrets into `.env.example`, tests or commits. If `.env` lacks `ENVIRONMENT=development` or a non-default JWT secret, add them locally only.
3. `cd backend && uv run alembic upgrade head`; `uv run uvicorn app:app --reload`; `cd frontend && npm run dev`.
4. Real end-to-end Print run for a figure-bearing lesson (spatial/process objective, e.g. an L-shaped floor plan or the water cycle). Inspect the booklet: do the figure's labels and the section text use the same words? Also run one lesson with **no** visual need and confirm zero figures appear.
5. Failure drills (run them, do not assume): bad Gemini key → `failed_recoverable`, specific safe error, retry offered, fix key + retry re-runs only figures; injected DB error in a section → fails fast, no 5-minute stall; restart backend mid-run → resumes or reports truthfully.
6. `python tools/agent/validate_repo.py --scope all` and `python tools/agent/check_architecture.py --format text` green; Gemini config tests green.

Iterate locally until section 5 is met, then open a PR.

## 5. Acceptance criteria

- [ ] Plan review shows each planned figure; the approved plan hash covers the `visual` objects.
- [ ] `grep -rn visual_required` on the live unit-lesson / shared-lesson / Print path returns nothing (legacy V3 studio hits are listed in the PR).
- [ ] An objective like "label the diagram of …" yields a `visual` object through the model's own reasoning, with no code rule involved; an objective with no visual need yields none.
- [ ] A `visual` with empty `must_show` is rejected by plan validation (repaired or rejected).
- [ ] Figures in the booklet == figures in the plan (exactly); composer cannot add or remove one (test).
- [ ] Writer output for a figure block contains the spec's labels; the label check records `label_missing` warnings when it does not (test), without blocking.
- [ ] Image request contains the plan spec plus caption/referring sentences; the work order is no longer built from caption/alt alone (test).
- [ ] Alt text comes from media (Gemini text part, else code fallback); writer does not produce it (test).
- [ ] Gemini generates the figures and they are visible in the rendered Print output; labels in the image match the section text on a real run.
- [ ] Progress shows planned / ready / failed per figure, with `pending` accepted until settled; nothing reads queued/ready while something failed.
- [ ] Forced figure failure → `failed_recoverable`, safe specific code in the status API, recovery action present; detail only in logs.
- [ ] Retry re-runs only failed figures.
- [ ] Section DB-failure drill: recorded and retryable within seconds.
- [ ] A fresh run's timer is under a minute, never hours.
- [ ] With QC off, `visual_quality` is `unreviewed`.
- [ ] Every item in the cut list is gone (grep shows no references); validation and architecture checks pass.

## 6. Delivery

Branch from `gemini-image-config` (already on origin). Small commits per area (A, B, C, cut list, E). No pushes to `main`; open a PR. The owner deploys to Railway and does one real Print run. Railway needs `IMAGE_PROVIDER=gemini` and `GEMINI_IMAGE_API_KEY` (already set per owner; legacy key names still work as fallback).

## 7. Out of scope

Media quality; SVG/chart renderers or a separate media service; parallel figure generation alongside the writer (deferred); splitting the planner into two calls (stays one call); GCS/storage; auth; class/student runtime; Learn path; plan approval/hash semantics beyond including `visual` in the hashed plan content.

## 8. Verify, do not assume

- Whether `TeachingPlanBlock` fields are mirrored in a draft/provider schema (two copies at ~L58 and ~L276) and the stored-plan migration: plans already stored without `visual` must still load (default null) and old approved plans must not be re-hashed.
- Plan review UI and `lesson_review` must still render when no slot carries a visual flag.
- Provider structured-output behaviour with the added nested object (planner uses DeepSeek via the structured call); if repair churn rises, keep `visual` flat.
- Whether the section writer sees the figure block's spec today; the writer packet may need the `visual` object added.
- Exact failure-handler location for the rollback bug (use the logged traceback).
- Whether the lite image model id works with the current `generate_content_stream` call and returns a text part.

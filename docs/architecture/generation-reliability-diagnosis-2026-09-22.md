# Generation reliability: architecture diagnosis

Date: 2026-09-22  
Repository inspected: `57177e66` (`codex/lectio-xplore-deploy`)  
Scope: deployed teacher lesson flow, current repository, retained live evidence  
Decision: diagnosis only; no generation code or production records changed

## Progress and evidence

- [x] Reproduce the previously reported Learn failure in three existing lessons.
- [x] Inspect one deployed successful Learn and Print lesson and exercise an interaction.
- [x] Start one fresh deployed preparation and inspect its server responses and review screen.
- [x] Trace planning, selection, writing, validation, retry, approval, and status code.
- [x] Compare the current observations with prior live campaigns and run focused tests.
- [x] Classify failure origin, recovery behavior, confidence, and next gates.

This is a small diagnostic sample, not a measured population failure rate. The first three lessons are older prepared records. The working lesson was prepared earlier. The fresh lesson was stopped at approval because its review panel was blank. Current Railway application logs were not available through the connected tools; the deployed API responses and browser Network panel supplied the live server evidence. The current repository was not matched to a deployment SHA, so source findings describe the inspected checkout and are identified as likely explanations where deployment identity matters.

## Executive assessment

The system has substantial contract and retry machinery, but reliability is limited by **boundaries between stages**. The three older records did not fail because Learn writing chose the wrong component: Learn writing never started. All three were rejected as needing Teaching Plan approval; the captured fraction request returned HTTP 409 because the handoff could not find an approved revision. The UI nevertheless labeled the plan approved. The fresh preparation reached a valid pending Teaching Plan, but its teacher review card was empty because the frontend displayed `teaching_review` metadata instead of `teaching_plan`. A previously completed Learn lesson did work, including answer checking, yet exposed internal planning prose as a learner title and section headings. Its Print preview displayed a figure placeholder and a long internal purpose as section text while the header still said Print was preparing.

The user's suspicion about structured input and output is partly confirmed. There are strict models, closed shortlists, and validation gates. They catch many invalid shapes. Some validation failures do get fed back to the model, but there is **no single end-to-end correction policy**. Provider-level structured-output failure can escape before the shared authoring repair loop receives a parsed payload. Post-authoring quality checks can fail after that loop has closed. A composition error can trigger a legal heuristic fallback rather than a model correction. A status or approval projection can be wrong even when the underlying generation contract is correct.

Overall assessment: **2/5 for dependable teacher-facing generation today**. This is an engineering judgment, not a statistical success rate. The strongest part is bounded structural planning and closed selection; the weakest parts are truthful review/admission state, semantic quality gates, and unified error routing.

## What happened in deployed runs

| Case | Observed state and timing | Boundary reached | Result |
| --- | --- | --- | --- |
| Seed germination, “Main Parts of a Seed” | Learn creation returned to its button with “Approve the Teaching Plan before generating Learn.” Plan screen claimed “Teaching plan approved.” | Approval handoff | No Learn output. |
| Photosynthesis, “Defining Photosynthesis” | Same visible Learn rejection. | Approval handoff | No Learn output. |
| Fraction division, “Whole Number ÷ Unit Fraction” | `POST /api/v1/v3/generations/.../realize-learn` returned HTTP 409 in about 3.3 s; body said approval required. Status API said `generation_status=failed`, `workflow_stage=blueprint_ready`, no Learn realization, and an ambiguous legacy Print realization. Issues API contained `OUTPUT_ERROR: could not convert string to float: '240;'`. | Approval handoff; older output error also present | No Learn output. The number parsing error's exact origin was not established. |
| Water movement, “Water enters the plant through root hair cells” | Existing approved plan and ready Learn output. Learn preview had 19 nodes; a choice answer returned “Correct.” Print preview had lesson content and an unavailable figure while the header still showed “Print · preparing.” | Full Learn path; partial Print delivery | Functionally usable Learn, with editorial and status defects. |
| Fresh “Xylem transports water up the stem” | Preparation reached `awaiting_teaching_approval` in about 17 s. API returned a full Teaching Plan, `teaching_validation.ok=true`, and pending review. UI displayed an empty plan card with an enabled “Approve plan” button. | Planning and review UI | Generation was left pending. No Learn/Print was attempted or approved from an unseen plan. |

The three older Learn rejections (with HTTP 409 confirmed for the fraction lesson) should not be extrapolated as a 100% failure rate for new lessons. A retained 2026-09-18 **local** campaign recorded two fresh nonvisual Learn outputs completing in about 99.5 s and 89.2 s, with one Print output ready in about 9.3 s. Those were not this Vercel deployment. The same campaign noted status disagreement during hydration. Its larger A–D campaign finished partially: classification and math were exercised through the learner flow, while a visual Print case remained queued and the live controlled recovery gate was not completed. Sources: [`new-lesson-sample-2026-09-18.md`](../lectio-reliability-health/evidence/live-campaign-2026-09-18/new-lesson-sample-2026-09-18.md), [`final-report.md`](../lectio-reliability-health/evidence/live-campaign-2026-09-18/final-report.md).

Focused tests on this checkout: `uv run pytest tests/authoring_correction/test_a02_shared_authoring_engine.py tests/planning/test_path_structural_repair.py tests/print_learn/test_composition_bridge.py -q` reported **12 passed, 1 skipped**. These tests prove selected repair/fallback behavior, not deployed end-to-end reliability.

## Where failures originate

```text
Unit and lesson objectives
  → structural plan and approved items
  → Teaching Plan and teacher approval ledger
  → Print/Learn admission
  → closed component and interaction choice
  → composition and writing
  → document validation, visuals, release
  → teacher/learner UI status
```

| Failure class | Earliest correct detection point | Current evidence | Origin judgment |
| --- | --- | --- | --- |
| Future concept required too early | Unit path and objective dependency validation | Fresh lesson 2 asks why water rises; lessons 3 and 4 separately teach water loss and transpiration pull. Its Teaching Plan follows lesson 2's objective by explaining pull from leaves. | **Path planning / curriculum sequencing** first. The writer is carrying an upstream objective. This is a pedagogical risk, not a proven schema violation. |
| Invalid plan JSON or slot/intent ownership | Planner output validation | Path and teaching planners use typed output, fixed slots, a second attempt with exact errors, and deterministic normalization. | **Planning output**; reasonably controlled for known invariants. |
| Missing approval on old record | Admission gate | Existing generation has no approved revision accessible to `accept_approved_teaching_revision`; `realize-learn` returns 409. | **Legacy state migration / handoff**. Learn selector and writer are not reached. |
| Blank plan review | Review UI | API has a populated `teaching_plan`, while the page renders only `teaching_review` fields. | **Frontend projection**. Approval can be offered without displaying instructional content. |
| Wrong content/interaction choice | Closed selector | Native selectors receive legal candidate IDs and allow one validation repair; sole candidate is selected without a model call. | **Selection** when it occurs, but no selection failure was demonstrated in this live sample. |
| Invalid authoring payload | Writer contract | Shared authoring engine parses, validates schema and registered validators, then sends previous output plus errors for up to two repairs within a three-call budget. | **Writing**; repair exists for this specific class. |
| Invalid provider-level structured response | Provider wrapper before shared engine parsing | `LLMAuthoringProvider` allows one library output retry; other nontransport exceptions are raised. The engine's own validation-error repair loop is never entered in that branch. | **Structured-output boundary**. Corrections are not consistently fed back by the outer authoring loop. |
| Invalid composition after engine validation | Composer semantic check | `_validate_composer_payload` runs after `AuthoringEngine.execute`; on error the default path uses a legal heuristic fallback. | **Composition/routing**; validity is preserved within the closed set, but the model's selection error is not directly corrected. |
| Late node quality failure | Document writer quality check | `_payload_quality_errors` runs after the authoring engine returns. It raises `INVALID_PAYLOAD` and marks the checkpoint ambiguous, expecting a separate durable retry. | **Post-write validation**; no immediate same-work-item correction prompt at that point. |
| Figure unavailable or output conversion error | Figure pipeline and Print render/export | Deployed Print preview displayed “Figure unavailable”; older math issue reported `float('240;')`. Prior local campaign recorded a visual provider 403. | **Media/rendering** for the placeholder; the precise old numeric-conversion root cause remains unproven. |
| Ready/preparing contradiction | Status projection | A ready Learn preview and populated Print preview coexisted with Print “preparing” header. Prior campaign reported similar header/card disagreement. | **Frontend/backend state projection and hydration**. |

## Current correction behavior

| Stage | Exact errors returned to model? | Attempts and stop condition | What happens after exhaustion |
| --- | --- | --- | --- |
| Unit path planner | Yes, contract errors and prior parsed draft. | Two fresh attempts. | `PathPlanningError`; no silent path acceptance. |
| Structural lesson planner | Yes, Pydantic/slot errors and prior parsed plan when available. | Two fresh attempts. | Failure is surfaced. |
| Teaching Plan planner | Yes, validation issues and recognized structured-output errors. | Two attempts; transport handled separately. | Failed preparation, eligible for stage-aware retry only if classified recoverable. |
| Capability selector | Yes, out-of-shortlist or missing-required choice. | Initial choice plus one constrained repair. | `SELECTOR_EXHAUSTED`; no open-ended choice. |
| Authoring engine payload | Yes, invalid payload and validator errors. | Initial plus up to two repairs; durable three-call cap. | `REPAIR_EXHAUSTED` / `INVALID_PAYLOAD`. |
| Provider output before parsed payload | Only one library-level output retry in the default authoring provider. | Provider exception can escape. | Outer engine does not receive a structured error to repair; the job may fail. |
| Composer post-validation | No direct correction at that point. | Default legal heuristic fallback if enabled. | Output can be structurally valid but editorial choice quality is not re-evaluated by the model. |
| Writer post-quality and final coherence | No uniform model feedback path. | Durable retry may later target a work item; coherence report currently checks a narrow deterministic set unless semantic issues are supplied. | Some defects stop generation; others can be marked ready because no semantic checker names them. |
| Print native failure | Error stage selects item, teaching, post-approval worker, or visual retry. | Failed terminal stops; recoverable retries resume bounded stage. | UI must show target and preserve valid sibling work. |
| Learn failure | Execution status becomes `failed_recoverable` where persistence succeeds; retry admits a new output identity for failed prior attempts. | Work item budgets/checkpoints constrain retry. | Not the same as correcting the exact model error unless a stage attaches it to the retry prompt. |

Relevant code: [`curriculum/agents.py`](../../apps/textbook-agent/backend/src/curriculum/agents.py), [`teaching_agent.py`](../../apps/textbook-agent/backend/src/print/generation/whole_lesson/teaching_agent.py), [`capability_selector.py`](../../apps/textbook-agent/backend/src/infra/authoring/capability_selector.py), [`engine.py`](../../apps/textbook-agent/backend/src/infra/authoring/engine.py), [`composer.py`](../../apps/textbook-agent/backend/src/document/composer.py), [`writer.py`](../../apps/textbook-agent/backend/src/document/writer.py), [`native_retry.py`](../../apps/textbook-agent/backend/src/print/generation/whole_lesson/native_retry.py), [`native_execution.py`](../../apps/textbook-agent/backend/src/learn/generation/native_execution.py).

Answer to “does an LLM structure error get fed back for correction?”: **sometimes, at specific nodes; not as a system-wide guarantee.** The path, structural, teaching, selector, and authoring-payload loops do this. A provider wrapper failure may never enter the authoring payload loop. A later quality checker may not feed its errors to the writer. Transport, auth, code defects, exhausted budgets, and missing approval should never be sent to the LLM as if they were malformed JSON.

## Architectural weaknesses to address first

1. **One authoritative lesson state across UI and admission.** Display approval only if an approved revision is present and consumable. Treat old `blueprint_ready`/legacy realization rows as explicit migration or reprepare cases. Use the same revision and hash for the Plan badge, button eligibility, and `realize-learn` gate. The current page's `ready` branch can present an approved shell even when teaching detail fetch fails; the handoff correctly rejects it. See [`plan/+page.svelte`](../../apps/textbook-agent/frontend/src/routes/units/%5Bid%5D/lessons/%5BlessonId%5D/plan/+page.svelte), [`realize_learn_handoff.py`](../../apps/textbook-agent/backend/src/application/unit_lesson/realize_learn_handoff.py), [`consumers.py`](../../apps/textbook-agent/backend/src/curriculum/teaching_plan/consumers.py).
2. **Review the actual plan.** The page derives its display object from `lessonApproach.teaching_review`; the API returns `teaching_plan` separately. Render arc, sections, blocks, learner actions, evidence, and scope before enabling approval. `teaching_review` remains approval metadata. This is a direct, code-confirmed cause of the fresh blank card.
3. **Validate dependency and scope at the path boundary.** Check whether each lesson's objective depends on a concept reserved for a later lesson. Where a causal explanation cannot be taught without that later concept, reorder, split, or explicitly permit a preview. A JSON schema cannot enforce this curricular invariant. The xylem sequence is the live example.
4. **Make errors first-class and stage-specific.** Persist `origin_stage`, `failure_class`, `contract_path`, `work_item_id`, `attempt`, `retryable`, `repairable`, and the exact validation errors. The public issue should distinguish approval/migration, planning, selection, writing, rendering, media, and delivery. “Approve the Teaching Plan” should not mask an old failed generation, nor should `OUTPUT_ERROR` imply the exact `240;` source without a stack trace.
5. **Give each structured call one repair owner.** Capture provider-output schema errors before they escape, normalize them into field/path errors, and send a fresh bounded correction prompt with the same approved inputs and legal candidate set. Preserve the current no-history-replay rule for providers that reject invalid assistant messages. Stop on auth, code, missing input, or repeated identical failures.
6. **Move quality gates next to the producing work item.** Composition semantic errors should be corrected within the composition budget before a declared fallback. Node quality errors should retry that node with its prior output and exact errors; final coherence should target only failed nodes/tasks. Never regenerate healthy siblings. A fallback should be visible in provenance and subject to an explicit quality check.
7. **Separate planning metadata from delivered copy.** `TeachingPlan.arc` is passed as a Learn title, and `specific_purpose` becomes section titles in Learn. The working preview showed paragraph-length teaching directions in learner and Print headings. Require concise learner-facing title/heading fields or deterministic human-readable titles, then validate length and audience. A structurally valid document should not automatically be rated publication-ready.
8. **Measure the whole funnel, not only request success.** Track preparation latency, model attempts, repair success, fallback rate, approval discrepancy, admission 409s, per-node writing failures, ready-but-placeholder figures, output review defects, and learner interaction success. Group by new vs legacy records and by Print vs Learn. This is necessary to identify the dominant source of breakdowns empirically.

## QC and retry policy for the target system

**Inline QC** should run after each producer: path dependencies, fixed structural slots, Teaching Plan intent/source ownership, closed selection, each writer payload, and each interaction's evaluability. A repair prompt must carry the exact validator path and the prior invalid output when safe to replay. One validation repair at planning/selection and at most two at a writer is a sensible starting budget; use observed recovery curves to tune it.

**Final QC** should verify document completeness, no planning-instruction leakage into learner text, cross-section coherence, assessment answer validity, figure readiness or an explicit degraded mode, and Print/ Learn preview rendering. It should report a named target (`node`, `task`, `figure`, or `section`) and a severity. It must not turn a partial or fallback output into plain `ready` without an appropriate quality state.

| Severity | Action |
| --- | --- |
| Warning | Preserve usable output; show provenance and teacher review cue. Examples: legal fallback or nonessential figure omission under an accepted degraded-mode policy. |
| Repairable error | Retry only the named work item with frozen approved inputs and exact errors. Revalidate after one correction; stop at the work item's durable budget. |
| Blocking dependency/approval error | Do not call an LLM. Repair state, migrate/reprepare, or request actual teacher review. |
| Terminal code/auth/contract mismatch | Stop immediately with a typed diagnostic and trace ID; route to engineering. Repeating the same model call cannot fix it. |

Expected effect: fewer full lesson reruns, faster recovery after a single malformed block, and clearer separation of content failure from infrastructure failure. It cannot guarantee that every model or provider call succeeds. The practical target is **zero silently accepted invalid outputs**, bounded retries, and a truthful, recoverable state for each failure.

## Ratings and confidence

Scale: 0 absent, 1 fragile, 2 partial, 3 workable with gaps, 4 strong, 5 verified across live failure/recovery cases. These are provisional engineering ratings informed by code plus the limited live sample.

| Area | Rating | Why |
| --- | ---: | --- |
| Path/structural contract enforcement | 3/5 | Typed plans and one exact-error repair; curricular dependency semantics remain weaker. |
| Teaching Plan validity | 3/5 | Closed intents/sources and repair; the fresh plan validated but can still reach a blank review UI and can inherit an overbroad objective. |
| Component/interaction selection | 3/5 | Closed shortlists and one repair; no live evidence here of selection failure or all component quality. |
| Writer structured output | 2.5/5 | Payload repair is explicit; provider-level and post-quality errors are not unified into that loop. |
| Failure recovery and checkpointing | 2.5/5 | Stage-aware retries and durable budgets exist; live failure-to-recovery was not observed in this run or the 2026-09-18 campaign. |
| Approval/status truthfulness | 1/5 | Three old records showed false approved affordance; fresh review showed no plan; Print header disagreed with preview. |
| Successful Learn delivery | 3/5 | One deployed lesson rendered and answered correctly; its headings leaked planning prose. Historical fresh local runs took about 1.5 minutes. |
| Print delivery | 2/5 | Populated preview existed, but figure unavailable and status preparing; current PDF visual QA was not performed. |
| Overall teacher-facing reliability | **2/5** | New nonvisual flow can work; old state, review, and quality boundaries remain unreliable. |

## Validation plan and open evidence

1. Run a fixed sample of at least 12 **new** lessons across science, mathematics, and a humanities subject, with nonvisual and visual variants. Record unique generation and realization IDs, stage timestamps, model attempts, repair count, fallback count, and final teacher-visible state. Keep old records as a separate migration cohort.
2. For each failed case, compare the first failing stage with the last successful stage. Classify planning, selection, writing, media/rendering, transport, and projection independently. Count only one failure per work item; track subsequent correction attempts separately.
3. Verify one controlled error at each boundary: invalid planner JSON, illegal component choice, writer schema error, post-write semantic defect, provider timeout, missing approval, and figure failure. Confirm exact-error feedback only for model-correctable classes, unchanged healthy siblings, exhausted-budget stop, and UI status accuracy after refresh.
4. Review at least three ready outputs for educational correctness, learner-facing language, answer keys, interaction evaluation, Print PDF layout, and missing media. A `ready` API response alone does not certify instructional quality.
5. Correlate deployed frontend/backend commit IDs with the repository before attributing every source-code mechanism to Vercel/Railway. Capture Railway trace IDs and redacted stack traces for the `240;` conversion error, which remains unlocalized here.

## Evidence boundaries

- The three old Learn rejections, including the confirmed HTTP 409 response for the fraction lesson, show an approval-admission problem at the Learn handoff. They do **not** show a Learn writer or component-selection failure.
- The old `float('240;')` issue is a separate recorded output error. Its stage and stack were not accessible, so labeling it a figure parser bug would overclaim.
- The fresh API returned a full Teaching Plan and a valid pending stage; the blank teacher card is directly explained by the inspected frontend field selection. The review was not approved.
- Historical local campaign timings and pass results are corroborating evidence, not deployed production metrics.
- No automated or manual test in this investigation proves zero-error generation, visual correctness, or full learner flow across subjects.

# Cursor proposal: remaining Xplore stability acceptance

Date: 2026-08-12  
Status: execution-ready proposal; live provider work requires explicit user authorization  
Authority: `PLAN.md`, the supplied XPLORE stability goal, and the whole-lesson proof protocol

## 1. Outcome

Finish the work needed to move Xplore from deterministic-green to evidence-backed
`STABLE` or `STABLE WITH KNOWN MINOR ISSUES`, then run the four official lessons
through the authenticated UI.

This is not a redesign. Most of the product is already verified. Cursor should:

1. close the remaining topology-recovery QC acceptance boundary;
2. make the evidence capture/verifier complete enough to prove the final gates;
3. run the five targeted live proofs in order;
4. run the four official lessons only after the targeted proofs are accepted;
5. produce a final requirement-by-requirement acceptance report.

The current verdict is `NOT YET STABLE` only because live acceptance evidence is
missing. Do not convert deterministic test success into a claim of live success.

## 2. Cursor start instructions

For this run, this file supersedes the old `apps/textbook-agent/CURSOR_GOAL.md`,
which belongs to an earlier reshape initiative. Do not execute that old goal.

Read, in order:

1. `apps/textbook-agent/AGENTS.md`
2. `apps/textbook-agent/agents/ENTRY.md`
3. `apps/textbook-agent/agents/project.md`
4. `apps/textbook-agent/agents/workflows/bugfix.md`
5. `PLAN.md`
6. `docs/evidence/whole-lesson-runs/stability-20260809/FINAL_ACCEPTANCE_AUDIT.md`
7. `docs/evidence/whole-lesson-runs/stability-20260809/LIVE_ACCEPTANCE_RUNBOOK.md`
8. this proposal

Maintain a visible checklist in this file or a new run report. Do not erase or
rewrite historical evidence. Append corrections with dates.

### Copy-ready Cursor launch prompt

```text
Work from:
C:\Projects\lectio\docs\evidence\whole-lesson-runs\stability-20260809\CURSOR_REMAINING_STABILITY_PROPOSAL.md

This proposal supersedes apps/textbook-agent/CURSOR_GOAL.md for this run.
Start with tickets R1-R3 only. Do not call any paid provider, click a live retry,
create a generation, mutate the DB, commit, push, or begin R4/R5 until R3 is green
and the user explicitly authorizes live provider calls. Preserve the dirty worktree.
Update the visible checklist and record exact commands/results as you work.
```

## 3. Locked decisions and non-negotiable invariants

- `/units` is the authenticated Home and current lesson-entry surface.
- Current generations are native whole-lesson contract v2. No Builder conversion.
- Blank `/studio` redirects to `/units`; `/studio?generation_id=...` is status/review.
- Historical v1 may remain readable but cannot create, convert, approve, retry, or
  execute new current work.
- Teacher approval remains a mandatory halt before form planning.
- Native retries resume the persisted checkpoint. They do not recompute upstream work.
- `failed_terminal` is absorbing. Recovery uses a fresh generation, not DB reclassification.
- Visual-only retry may touch only visual state, visual events, document revision, and
  final hash proof. It must not rerun items, teaching, form planning, or nonvisual writers.
- A flagged, rejected, missing, or unreviewed visual cannot be `ready`.
- A material visual patch invalidates previous final hashes. `ready` requires a fresh
  persistence reload at the current revision with non-empty equal canonical hashes.
- Native V2 viewer/PDF bypasses legacy adapters. `edition=teacher|student` is authoritative.
- Teacher PDF contains the answer key exactly once; student PDF contains none.
- `llm_calls` is the authoritative call ledger. Never synthesize a generation ID from a trace ID.
- No authentication bypass, hidden progression endpoint, manual DB progression, legacy
  conversion, or manual viewer navigation may count as final evidence.
- Do not increase retry counts, weaken validators, or add keyword-specific Water Cycle code.
- Do not touch ports 5174 or 8001. Use frontend 5173 and backend 8000.
- Do not push. Do not commit unless the user explicitly asks.

## 4. Current verified baseline — do not redo as implementation work

- Backend full suite previously passed: 1,080 tests.
- Frontend full suite previously passed: 81 files / 341 tests.
- Svelte diagnostics: 0 errors / 0 warnings.
- Production build, architecture validator, prompt verifier, and tooling gates passed.
- Latest topology/visual boundary: 75 tests passed.
- Latest topology-recovery suite: 11 tests passed.
- Frontend and backend health probes returned HTTP 200.
- Native routing, quarantine, retries, leases, PDF selection, telemetry plumbing,
  visual hash invalidation, and ready/reload fencing are deterministic-green.

Cursor may rerun these gates after its changes. It must not redesign already-green
subsystems unless a new focused regression or live replay proves a concrete defect.

## 5. Remaining work map

| Ticket | Outcome | Paid/live work? | Dependency |
| --- | --- | --- | --- |
| R1 | Topology recovery uses the final model-backed visual QC before upload/completion | No provider call in tests | none |
| R2 | Evidence capture and verifier prove hashes, telemetry, PDFs, and zero legacy runtime | No | R1 preferred |
| R2A | Development-only one-shot form-timeout proof hook is exact-generation fenced | No provider call | R2 |
| R3 | Deterministic confidence gate is green | No | R1-R2A |
| R4 | Five targeted browser proofs pass | Yes; explicit authorization | R3 |
| R5 | Four official browser lessons pass | Yes; explicit authorization | R4 accepted |
| R6 | Final Sol-style acceptance audit and issue classification | No new provider calls | R5 |

## 6. Ticket R1 — close topology-recovery visual-QC acceptance

### Why this exists

Topology recovery now validates topology shape, identity, labels/evidence, and a
renderable asset. Its normal dispatch path still needs to prove that the final
deterministic raster goes through the same model-backed image-quality review as
ordinary visuals before upload/completion. A deterministic integrity check is
necessary but is not sufficient evidence of classroom visual quality.

### Expected behavior

The product path must be:

```text
persisted authoritative source
  -> validated/reused topology
  -> deterministic final raster bytes
  -> model-backed visual QC on those exact bytes
  -> QC accept only
  -> generation-specific upload
  -> apply_visual_completion
  -> revision increment
  -> fresh reload/equal hashes
  -> ready
```

On QC flag/reject/error/invalid response:

```text
awaiting_visuals + retry_visuals
no apply_visual_completion
no ready transition
no final hash proof
no shared accepted cache write
no upstream rerun
```

Topology recovery must remain image-provider-free. A visual-QC model call is allowed;
an xAI/image-provider call is not.

### Production files to modify

Primary:

- `apps/textbook-agent/backend/src/planning/whole_lesson/visual_topology_recovery.py`
  - preserve the final PNG bytes until QC completes;
  - call QC before generation-specific upload and before `apply_visual_completion`;
  - require an explicit accepted verdict;
  - keep deterministic integrity QC as preflight, not final classroom acceptance;
  - emit/persist QC outcome, reasons, correction hint, latency/trace metadata;
  - retain fail-closed behavior for null, malformed, flagged, rejected, and errored verdicts.
- `apps/textbook-agent/backend/src/planning/whole_lesson/visual_dispatch.py`
  - construct/reuse the authoritative `VisualGeneratorWorkOrder` for topology QC;
  - inject the model-QC adapter into topology recovery;
  - preserve provider isolation for both top-level and asset-only request IDs;
  - keep topology requests out of ordinary `execute_visual` dispatch.

Touch only if the adapter genuinely requires it:

- `apps/textbook-agent/backend/src/media/qc/visual_qc.py`
  - expose a small reusable QC call accepting the final raster plus the existing
    `VisualGeneratorWorkOrder`; do not change its accept/flag/reject policy.
- `apps/textbook-agent/backend/src/v3_execution/models.py`
  - only if a typed QC context field is unavoidable; prefer the current models.

Do not modify by default:

- `repository.py`, `native_status.py`, `router.py`, frontend pages, or DB schemas.
  Their current contracts are green. Touch them only when a new failing test proves
  a missing field or transition.

### Tests to modify/add

- `apps/textbook-agent/backend/tests/planning/test_visual_topology_recovery.py`
  - final raster bytes passed to QC are the bytes uploaded/completed;
  - QC accept permits exactly one completion;
  - QC flag/reject/error/malformed verdict invokes zero completion;
  - QC occurs before upload;
  - no xAI/image-provider executor call;
  - asset-only request ID remains isolated from normal provider dispatch;
  - resumed topology is revalidated and QC-reviewed.
- `apps/textbook-agent/backend/tests/planning/test_phase05_visual_dispatch.py`
  - product dispatch injects the QC adapter and returns `awaiting_visuals` on flag.
- `apps/textbook-agent/backend/tests/planning/test_visual_dispatch_failure.py`
  - flagged topology recovery keeps hashes null/invalid and upstream outcomes unchanged;
  - accepted topology recovery increments revision and re-establishes equal hashes.
- `apps/textbook-agent/backend/tests/media/test_visual_qc_prompt.py`
  - final topology raster criteria preserve exact labels, topology semantics, and
    unwanted-text checks.

### Targeted command

```powershell
cd C:\Projects\lectio\apps\textbook-agent\backend
$tests = @(
  'tests\planning\test_visual_topology.py',
  'tests\planning\test_visual_topology_recovery.py',
  'tests\media\test_topology_renderer.py',
  'tests\media\test_diagram_compositor.py',
  'tests\media\test_visual_qc_prompt.py',
  'tests\planning\test_phase05_visual_dispatch.py',
  'tests\planning\test_visual_dispatch_failure.py',
  'tests\v3_execution\test_v3_execution_core.py'
)
.\.venv\Scripts\python.exe -m pytest @tests -q --tb=short
.\.venv\Scripts\ruff.exe check `
  src\planning\whole_lesson\visual_topology_recovery.py `
  src\planning\whole_lesson\visual_dispatch.py `
  tests\planning\test_visual_topology_recovery.py
```

### Acceptance criteria

- The production dispatch path cannot return `ready` without explicit model-QC accept.
- QC sees the final deterministic raster, not the original provider image or metadata only.
- Flag/reject/error leaves the generation retryable and hashes invalid.
- No ordinary image-provider execution occurs during topology recovery.
- Focused tests and Ruff pass.

## 7. Ticket R2 — complete evidence capture and acceptance verification

### Why this exists

The current capture script writes core planning artifacts but does not yet prove all
final acceptance requirements. Cursor should make one command produce the evidence
needed to judge a run without manual DB archaeology.

### Production/tooling files to modify or add

- Modify `apps/textbook-agent/backend/scripts/capture_whole_lesson_evidence.py`.
- Modify `apps/textbook-agent/backend/tests/test_capture_whole_lesson_evidence_script.py`.
- Add **new** `apps/textbook-agent/backend/scripts/verify_whole_lesson_acceptance.py`.
- Add **new** `apps/textbook-agent/backend/tests/test_verify_whole_lesson_acceptance_script.py`.
- Update `docs/evidence/whole-lesson-runs/_templates/RUN_MANIFEST_TEMPLATE.yaml`.
- Update `docs/evidence/whole-lesson-runs/_templates/INPUT_OUTPUT_TRACE_TEMPLATE.md`
  only if a required trace field is missing.
- Update `docs/evidence/whole-lesson-runs/stability-20260809/LIVE_ACCEPTANCE_RUNBOOK.md`
  with the exact capture and verify commands.

Do not modify `run_whole_lesson_proof.py` to bypass the browser requirement. It may
remain a diagnostic/reference helper, but its proof-user JWT/API progression does not
count as an official final matrix run.

The authenticated browser owns screenshots and UI-exported PDFs. The capture script
may accept explicit local artifact paths such as `--generation-page`, `--teacher-pdf`,
and `--student-pdf`, validate them, hash them, and copy them into the run folder. It
must not manufacture those artifacts through hidden API progression or claim a
missing browser artifact was captured.

### Capture requirements

For a supplied generation ID and run slug, capture at minimum:

- native identity: contract version, `native_whole_lesson`, provenance IDs;
- stage/status timeline and full native event stream;
- lesson packet, teaching/form prompts, raw responses, parsed plans, validation, QC;
- approved item records, writer call ledger, visual work orders, topology/QC history;
- persisted generation record and fresh-session reloaded `LectioDocumentV2`;
- current document revision;
- non-empty `document_sha256`, `reloaded_sha256`, and `reload_verified`;
- provider ledger from `llm_calls`: call/trace/generation/user IDs, caller/node/stage,
  provider/model/slot, attempt, timestamps/duration, outcome, retryable/error class,
  tokens/cost where available;
- total stage wall time, parallel writer wall time, cumulative provider time;
- teacher and student UI-exported PDF paths, byte sizes, SHA256, page counts;
- answer-key count: teacher exactly once, student zero;
- visual presence in viewer and both PDFs;
- zero-current-legacy audit: no Builder/stage2 requests and no `EditableLessonModel`
  whose `source_generation_id` is the current generation or variant ID;
- missing-artifact list and explicit pass/fail reasons.

Do not store access tokens, API keys, signed secrets, or raw environment values.

### Verifier behavior

The verifier accepts a run directory and exits:

- `0`: all final gates represented by that run pass;
- `2`: evidence is incomplete or a gate fails;
- nonzero error: malformed/unreadable evidence.

It must fail when:

- native identity is missing or false;
- final stage is not `ready`;
- hashes are empty, unequal, stale, or `reload_verified` is false;
- visual QC is flagged/rejected/missing for a required visual;
- teacher/student PDF evidence is absent or answer visibility is wrong;
- telemetry rows lack generation attribution for current-path calls;
- legacy current-generation records or requests exist;
- a required protocol artifact is absent.

### Targeted command

```powershell
cd C:\Projects\lectio\apps\textbook-agent\backend
.\.venv\Scripts\python.exe -m pytest `
  tests\test_capture_whole_lesson_evidence_script.py `
  tests\test_verify_whole_lesson_acceptance_script.py `
  tests\services\test_telemetry_service.py `
  tests\planning\test_native_report_projection.py `
  -q --tb=short
.\.venv\Scripts\ruff.exe check `
  scripts\capture_whole_lesson_evidence.py `
  scripts\verify_whole_lesson_acceptance.py `
  tests\test_capture_whole_lesson_evidence_script.py `
  tests\test_verify_whole_lesson_acceptance_script.py
```

### Acceptance criteria

- Fixture tests cover a complete pass, every individual required-field failure, unsafe
  run slugs, telemetry gaps, hash mismatch, PDF answer mismatch, and legacy leakage.
- Capture is read-only with respect to generation state.
- Output contains no secrets.
- A human can decide the run from the captured folder without querying the DB again.
- Missing browser screenshot/PDF inputs remain explicit failures; tooling never
  substitutes API-only artifacts for them.

## 8. Ticket R2A — deterministic form-timeout proof control

### Why this exists

Targeted proof A must demonstrate a real persisted form-timeout boundary and a
visible checkpoint retry. Waiting for a random network timeout wastes credits and is
not reproducible. The existing `failure_injection.py` is writer-block-only: its
environment switch does not supply a generation ID or block index, and it cannot
inject a form timeout. Do not misuse it as evidence without extending its contract.

### Production files to modify

- `apps/textbook-agent/backend/src/planning/whole_lesson/failure_injection.py`
  - preserve the existing writer-block behavior;
  - add an explicit node/stage target, with `planning_forms` as an allowed proof target;
  - parse an exact generation ID and node from dedicated environment variables;
  - require the existing master switch `XPLORE_NATIVE_FAILURE_INJECTION=true`;
  - default disabled and fail closed on incomplete/unknown configuration;
  - retain one-shot behavior and expose no HTTP/API configuration surface.
- `apps/textbook-agent/backend/src/planning/whole_lesson/executor.py`
  - immediately before `run_form_planner`, trip only the exact-generation
    `planning_forms` hook;
  - append a clearly named `proof_fault_injected` event with node and fault class;
  - raise a real `TimeoutError` so the normal worker failure policy persists
    `TIMEOUT`, `retryable=true`, and `failed_recoverable`;
  - do not call the form provider on the injected attempt.
- Update `apps/textbook-agent/backend/.env.example` with commented, unmistakably
  development/test-only variables and a warning that they are forbidden in final
  matrix or production-like environments.

Suggested environment contract:

```text
XPLORE_NATIVE_FAILURE_INJECTION=true
XPLORE_NATIVE_FAILURE_GENERATION_ID=<exact UUID>
XPLORE_NATIVE_FAILURE_NODE=planning_forms
XPLORE_NATIVE_FAILURE_ONCE=true
```

The hook must refuse to enable under production-like `APP_ENV` values. Do not add a
browser button, admin endpoint, database flag, or generic arbitrary-exception input.

### Tests to modify/add

- `apps/textbook-agent/backend/tests/planning/test_phase02_resume_and_assembly.py`
  - existing writer failure semantics remain unchanged.
- `apps/textbook-agent/backend/tests/planning/test_pre_worker_failure_sync.py`
  - injected form timeout persists `failed_recoverable`, `TIMEOUT`, and
    `retryable=true` through the real worker failure boundary;
  - the form model mock has zero calls;
  - wrong generation, wrong node, disabled configuration, or second occurrence does
    not inject;
  - production-like environment refuses activation.
- `apps/textbook-agent/backend/tests/planning/test_native_retry_pre_worker.py`
  - one visible/native retry acceptance requeues the form checkpoint;
  - the subsequent worker claim starts at `planning_forms` exactly once;
  - item and teaching artifacts/call counts remain unchanged.

### Targeted command

```powershell
cd C:\Projects\lectio\apps\textbook-agent\backend
.\.venv\Scripts\python.exe -m pytest `
  tests\planning\test_phase02_resume_and_assembly.py `
  tests\planning\test_pre_worker_failure_sync.py `
  tests\planning\test_native_retry_pre_worker.py `
  tests\planning\test_phase02_queue_and_lease.py `
  -q --tb=short
.\.venv\Scripts\ruff.exe check `
  src\planning\whole_lesson\failure_injection.py `
  src\planning\whole_lesson\executor.py `
  tests\planning\test_pre_worker_failure_sync.py
```

### Live-proof procedure and cleanup

1. Create the targeted generation normally and stop at teaching approval.
2. Restart only the backend with the four exact variables above, targeting that UUID.
3. Approve teaching through the visible UI. Confirm `proof_fault_injected` and a
   persisted form `TIMEOUT`; confirm no form-provider call was made.
4. Stop the backend, remove every injection variable, restart, and verify the startup
   log reports failure injection disabled.
5. Click the visible retry action once and complete from the form checkpoint.
6. Record before/after upstream call counts and the exact event/timestamps.

The four official final lessons must start only after all injection variables are
absent and a negative configuration check is captured. Never count a fault-injected
generation as one of the four official lessons.

### Acceptance criteria

- The injected attempt consumes zero provider credits.
- Only the exact generation and `planning_forms` boundary can trip.
- Normal classification, repository transitions, retry endpoint, queue, and worker
  lease paths are used; no direct DB mutation advances the run.
- Removing the environment variables fully disables the hook after restart.
- Tests prove no regression to the existing writer-only injection.

## 9. Ticket R3 — deterministic confidence gate before credits

Run this only after R1 and R2 are complete.

### Backend focused gate

```powershell
cd C:\Projects\lectio\apps\textbook-agent\backend
$nativeTests = @(
  'tests\planning\test_native_only_routing.py',
  'tests\planning\test_native_status_payload.py',
  'tests\planning\test_native_retry_pre_worker.py',
  'tests\planning\test_native_retry_durability.py',
  'tests\planning\test_native_retry_lease_fencing.py',
  'tests\planning\test_phase02_queue_and_lease.py',
  'tests\planning\test_phase02_worker_failure_policy.py',
  'tests\planning\test_phase02_resume_and_assembly.py',
  'tests\planning\test_pre_worker_failure_sync.py',
  'tests\planning\test_phase05_visual_dispatch.py',
  'tests\planning\test_visual_dispatch_failure.py',
  'tests\planning\test_visual_topology.py',
  'tests\planning\test_visual_topology_recovery.py',
  'tests\media\test_topology_renderer.py',
  'tests\media\test_diagram_compositor.py',
  'tests\media\test_visual_qc_prompt.py',
  'tests\planning\test_phase02_visual_pdf_routes.py',
  'tests\generation\test_native_pdf_exports.py',
  'tests\generation\test_pdf_export_service.py',
  'tests\services\test_telemetry_service.py',
  'tests\test_capture_whole_lesson_evidence_script.py',
  'tests\test_verify_whole_lesson_acceptance_script.py'
)
.\.venv\Scripts\python.exe -m pytest @nativeTests -q --tb=short
.\.venv\Scripts\ruff.exe check src tests scripts
```

### Frontend focused gate

Use the installed pnpm directly if Corepack signature verification fails:

```powershell
cd C:\Projects\lectio
$node = 'C:\Program Files\nodejs\node.exe'
$pnpm = 'C:\Program Files\nodejs\node_modules\pnpm\bin\pnpm.cjs'
& $node $pnpm --dir apps/textbook-agent/frontend exec vitest run `
  'src/lib/api/client.test.ts' `
  'src/lib/api/v3.test.ts' `
  'src/lib/auth/routing.test.ts' `
  'src/routes/units/page.test.ts' `
  'src/routes/units/[id]/page.test.ts' `
  'src/routes/studio/page.test.ts' `
  'src/routes/studio/generations/[id]/page.test.ts' `
  'src/routes/studio/print/[id]/page.test.ts'
& $node $pnpm --dir apps/textbook-agent/frontend check
```

### Repository gate

```powershell
cd C:\Projects\lectio\apps\textbook-agent
backend\.venv\Scripts\python.exe tools\agent\check_architecture.py --format text
backend\.venv\Scripts\python.exe tools\agent\validate_repo.py --scope all

cd C:\Projects\lectio\apps\textbook-agent\backend
.\.venv\Scripts\python.exe scripts\verify_whole_lesson_prompts.py
```

If `validate_repo.py --scope all` already executes full suites, record its exact output.
Do not claim the full gate passed from focused tests alone.

### R3 GO gate

Proceed to live work only when:

- every focused test passes;
- frontend checks pass;
- architecture and prompt verification pass;
- no unexplained P0/P1 issue exists;
- services are healthy on 5173/8000;
- the user explicitly authorizes paid/live provider calls.

## 10. Ticket R4 — five targeted live proofs

### Authorization gate

Before any paid call, write in the run report:

```text
LIVE PROVIDER CALLS AUTHORIZED BY USER: yes
timestamp:
authorized scope: targeted proofs only | targeted proofs plus final matrix
```

If authorization is absent, stop. Do not infer it from the server being open.

Use the authenticated in-app browser. If login is shown, pause for the user. Do
not manufacture a token or use the proof-runner user.

### A. Form timeout and checkpoint retry

Use Ticket R2A's exact-generation, one-shot hook. Do not wait for a random timeout,
change the model URL to an arbitrary service, or consume a provider request merely to
manufacture the failure. Remove the hook configuration and restart before clicking
the visible retry.

Expectation:

```text
form timeout
-> failed_recoverable
-> UI next_action=retry_form/retry_native as projected by backend
-> one visible retry click
-> resume at form checkpoint
-> no item or teaching calls after retry cutoff
-> ready
-> automatic viewer navigation
```

Evidence:

- before/after counts and latest timestamps for item, teaching, and form calls;
- status/error/next_action before retry;
- retry acceptance event and worker lease token;
- final current revision and equal hashes.

Stop on terminal classification, automatic retry loops, or any upstream rerun.

### B. Home/New native-only

Expectation:

- start at `/units`;
- click the visible New unit/lesson action;
- create through the normal unit/path UI;
- generation has contract v2, `native_whole_lesson=true`, path provenance;
- no Builder page, Builder API, direct stage1 endpoint, or editable legacy record;
- complete one lesson through the normal UI.

Files to change only if browser evidence contradicts current tests:

- `frontend/src/routes/units/+page.svelte`
- `frontend/src/routes/units/[id]/+page.svelte`
- `frontend/src/routes/studio/+page.svelte`
- `backend/src/planning/routes.py`
- `backend/src/planning/bridge.py`

Any change requires a matching existing focused test file beside the route.

### C. Ready auto-navigation

Expectation:

- remain on `/studio?generation_id=<id>`;
- do not manually open the viewer;
- when backend stage becomes `ready`, the UI navigates exactly once to
  `/studio/generations/<id>`;
- polling/stream hydration stops after ready.

Files to change only on a reproduced browser failure:

- `frontend/src/routes/studio/+page.svelte`
- `frontend/src/routes/studio/page.test.ts`

### D. Real visual plus visual-only recovery

Use a lesson whose approved requirement genuinely needs a visual. Water Cycle may be
used as a targeted visual proof, not as one of the four final lessons.

Stop gates:

1. Structural review: required slot has `visual_required=true`.
2. Teaching review: accepted visual intent and concrete authoritative brief.
3. Form plan: required slot selects `figure` and persists `visual_pending`.
4. First image-provider result: real configured provider call is attributed.
5. If QC accepts, continue to viewer/PDF/hash proof.
6. If QC flags, use exactly the visible visual-only retry. Topology recovery may use
   the persisted internal asset but must make zero further image-provider calls and
   must receive final model-QC acceptance.

Acceptance:

- real provider call exists for the initial asset;
- final visual is QC accepted and human-inspected;
- exact labels are correct and legible; no extra/garbled text;
- semantic entities, relationships, movement, and exclusions are correct;
- only visual-stage telemetry appears after retry cutoff;
- document revision increases;
- hashes were invalidated during retry, then repopulated equal after fresh reload;
- viewer shows the visual;
- teacher and student PDFs both show the visual;
- teacher answer key exactly once; student answer key zero.

If final model QC flags the topology result, stop. Do not add another image-provider retry
or weaken QC. Record the defect for architecture review.

### E. Worker restart/reclaim

Existing evidence in `RECOVERY_RUN_5C254377.md` may be accepted if it contains all
required fields. Otherwise perform one controlled proof at a recoverable checkpoint:

- capture owner, lease token, heartbeat, and checkpoint;
- stop only the verified worker process;
- wait for lease expiry;
- restart the worker normally;
- capture new owner/token and reclaim event;
- prove stale owner cannot mutate;
- prove continuation from checkpoint without DB edits or upstream rerun.

Do not kill the frontend, database, or unrelated processes.

### Targeted proof acceptance

All A-E must be marked `PASS` by evidence review before R5. A deterministic test,
historical diagnostic, or manually corrected DB row is not a substitute.

## 11. Ticket R5 — four official final browser lessons

Run exactly these four new lessons through the authenticated normal UI:

1. Grade 4 Science — **Why Plants Need Light to Make Food**
   - destination objective: `Explain why plants need light to make food.`
   - starting knowledge: roots/stems/leaves; living things need food to grow.
2. Grade 6 Mathematics — **Understanding Equivalent Fractions**
   - destination objective: `Identify and explain equivalent fractions using visual models.`
   - starting knowledge: compare fractions with like denominators.
3. Grade 8 Economics — **How Supply and Demand Affect Price**
   - destination objective: `Explain how changes in supply and demand affect the price of a good.`
   - starting knowledge: markets sell goods/services; price is what buyers pay.
4. Grade 7 English — **Distinguishing a Claim from Supporting Evidence**
   - destination objective: `Distinguish a claim from supporting evidence in a short text.`
   - starting knowledge: main idea; authors make points in writing.

### Procedure for each lesson

1. Create the unit from `/units`.
2. Generate and approve the path through visible UI.
3. Prepare the selected conceptual lesson.
4. Review structural plan and stop on contract drift.
5. Approve structural plan through UI.
6. Review teaching plan last brief first, then first brief, then the arc.
7. Stop on missing authority, object-ID leak, unsupported content, or weak final brief.
8. Approve teaching plan through UI.
9. Let form/writers/assembly run normally.
10. Stay on Studio and capture automatic ready navigation.
11. Inspect the reloaded viewer document.
12. Export teacher and student PDFs through UI.
13. Run evidence capture and verifier.
14. Record conclusion before starting the next lesson.

Do not run lessons in parallel on the shared server/DB. Do not start Run 2 until Run 1
has a completed evidence folder and verifier result.

### Evidence folders

Use only:

- `docs/evidence/whole-lesson-runs/run-01-science/`
- `docs/evidence/whole-lesson-runs/run-02-mathematics/`
- `docs/evidence/whole-lesson-runs/run-03-economics/`
- `docs/evidence/whole-lesson-runs/run-04-english/`

Existing blocked scaffolds may be appended/replaced only with artifacts from the new run.
Do not relabel historical failures as successes.

### Required artifacts per run

The folder must satisfy
`docs/authority/whole-lesson-e2e-pack-v1.2/04_PROOF_RUNS/FOUR_RUN_PROOF_PROTOCOL.md`,
including artifacts `00` through `39`. Additional telemetry/topology/legacy-audit JSON
files are allowed and encouraged.

At minimum verify:

- `00-manifest.yaml`
- native input/path/provenance artifacts;
- lesson packet and exact prompts/raw responses;
- teaching/form plans, validation, QC, approval;
- writer ledger/prompts/results;
- approved items and question assembly;
- visual work orders/topology/QC;
- event stream;
- persisted generation and fresh reloaded document;
- document validation and input-output trace;
- quality scorecard;
- authenticated generation-page screenshot;
- teacher and student PDFs;
- timing/cost/telemetry;
- run log and conclusion;
- zero-current-legacy audit.

### Per-run PASS criteria

- Native contract v2 and `native_whole_lesson=true` from creation onward.
- No current legacy/Builder/stage2 request or editable record.
- Teaching/form plans persisted and reloaded.
- Approved items are the only question source.
- All required blocks ready; no terminal or silently omitted block.
- Required visual, if selected, is QC accepted and renders correctly.
- Final viewer uses the persisted/reloaded document.
- `document_sha256 == reloaded_sha256`, both non-empty.
- `reload_verified=true` at current document revision.
- Teacher PDF answer key exactly once; student PDF none.
- Provider/model/stage/attempt/latency/outcome attribution complete.
- No P0/P1 defect.
- Evidence verifier exit code 0.

If any run fails, stop the matrix. Diagnose and fix the concrete issue, rerun focused and
full deterministic gates, then create a new run. Do not continue to collect four partial runs.

## 12. Ticket R6 — final audit and decision

Update:

- `docs/evidence/whole-lesson-runs/stability-20260809/FINAL_ACCEPTANCE_AUDIT.md`
- `docs/evidence/whole-lesson-runs/stability-20260809/DETERMINISTIC_FINAL_GATE.md`
- `docs/evidence/whole-lesson-runs/stability-20260809/LIVE_ACCEPTANCE_RUNBOOK.md`
- a **new** `docs/evidence/whole-lesson-runs/stability-20260809/FINAL_MATRIX_SUMMARY.md`

The final summary must contain a table with one row per requirement in `PLAN.md` section 11
and direct evidence paths. Classify every issue:

- P0: unsafe/data-loss/security or architecture-invalid;
- P1: core workflow cannot complete or evidence is false;
- P2: material but bounded defect with safe workaround;
- P3: cosmetic/diagnostic/documentation issue.

Decision rules:

- `STABLE`: every required gate passes; no P0/P1 remains.
- `STABLE WITH KNOWN MINOR ISSUES`: every required gate passes; only P2/P3 remain.
- `NOT YET STABLE`: any required proof is missing or any P0/P1 remains.

Do not edit `PLAN.md` checkboxes to passed without direct evidence paths.

### Stop conditions

Stop the dependent track and write a blocker when any of these occurs:

- R1 appears to require weakening QC, changing retry counts, or reintroducing an
  image-provider call into topology recovery.
- Final raster bytes cannot be QC-reviewed before upload without changing the
  repository/document contract. Record the exact seam and request architecture review.
- Evidence capture would require storing a token, API key, signed secret, or raw env.
- A DB migration or destructive cleanup appears necessary.
- A live run reaches `failed_terminal`, silently reruns upstream work, auto-retries
  without a visible action, or touches a legacy current-product path.
- Authentication expires. Pause for manual login; do not bypass it.
- A required browser artifact is unavailable. Mark it missing; do not fabricate it.
- A provider/QC result is ambiguous. Treat it as not accepted.
- Run N fails a P0/P1 gate. Stop before Run N+1.

Independent documentation or deterministic test work may continue after a live-run
blocker, but the matrix must not.

## 13. Full final validation

After all code changes and before final judgment:

```powershell
cd C:\Projects\lectio\apps\textbook-agent\backend
.\.venv\Scripts\python.exe -m pytest -q --tb=short
.\.venv\Scripts\ruff.exe check src tests scripts

cd C:\Projects\lectio
$node = 'C:\Program Files\nodejs\node.exe'
$pnpm = 'C:\Program Files\nodejs\node_modules\pnpm\bin\pnpm.cjs'
& $node $pnpm --dir apps/textbook-agent/frontend check
& $node $pnpm --dir apps/textbook-agent/frontend test
& $node $pnpm --dir apps/textbook-agent/frontend build
& $node $pnpm --dir packages/lectio-page check
& $node $pnpm --dir packages/lectio-page test

cd C:\Projects\lectio\apps\textbook-agent
backend\.venv\Scripts\python.exe tools\agent\check_architecture.py --format text
backend\.venv\Scripts\python.exe tools\agent\validate_repo.py --scope all

cd C:\Projects\lectio\apps\textbook-agent\backend
.\.venv\Scripts\python.exe scripts\verify_whole_lesson_prompts.py
```

Record exact commands, exit codes, test counts, warnings, and corrected PowerShell syntax.

## 14. Expected final deliverable

Cursor returns:

1. files changed and why;
2. targeted and full validation results;
3. A-E targeted proof table with direct evidence paths;
4. four-run matrix table with generation/unit/lesson IDs and verdicts;
5. provider/latency/attempt summary;
6. hash/reload/PDF/answer visibility summary;
7. zero-current-legacy audit;
8. P0-P3 issue list;
9. final `STABLE`, `STABLE WITH KNOWN MINOR ISSUES`, or `NOT YET STABLE` decision;
10. exact remaining blocker if the decision is not stable.

## 15. Immediate Cursor checklist

- [ ] Read the authority files and record starting SHA/dirty tree without resetting it.
- [ ] Confirm no other worker or provider run is active.
- [ ] Implement R1 model-backed QC-before-upload/completion.
- [ ] Add and pass R1 regressions.
- [ ] Implement R2 evidence capture and verifier.
- [ ] Add and pass R2 regressions.
- [ ] Implement and validate R2A's exact-generation form-timeout proof control.
- [ ] Confirm the fault-control environment is absent before any final-matrix run.
- [ ] Run R3 deterministic confidence gate.
- [ ] Obtain explicit user authorization for provider credits.
- [ ] Run and accept targeted proofs A-E in order.
- [ ] Run official lessons 1-4 sequentially through authenticated UI.
- [ ] Capture and verify every evidence folder.
- [ ] Run full final validation.
- [ ] Produce the final matrix summary and acceptance decision.

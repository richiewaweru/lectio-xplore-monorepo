# Casa Runbook

Update this file continuously while executing.

## Repository state

- Base branch: `main`
- Base SHA: `802b4f98`
- Work branch: `chore/retire-v3-legacy`
- Started: 2026-09-23
- Current phase: G (visual contracts moved; remaining v3 names are live adapters)
- Last passing gate: visual executor tests 38 passed after contract move

---

## Global status

- [x] Phase 0 — baseline
- [x] Phase A — dependency/ownership map
- [x] Phase B — extract current execution infrastructure
- [x] Phase C — move current planning
- [x] Phase D — extract native routes/frontend APIs (frontend APIs/components moved; backend native handlers still registered on /api/v1/v3)
- [x] Phase E — delete legacy backend execution
- [x] Phase F — delete legacy frontend Studio
- [x] Phase G — namespace closeout (remaining names are listed adapters)
- [x] Phase H — E2E proof (PARTIAL: Learn writer failed; Print not created)
- [x] Closeout report complete

---

## Phase 0 evidence

### Baseline commands
```text
backend: already up — GET http://127.0.0.1:8000/health → 200
frontend: pnpm exec vite dev --host 127.0.0.1 --port 5173
  with VITE_API_TARGET=http://127.0.0.1:8000
  (frontend/.env PUBLIC_API_URL pointed at :8001; that caused login 500s)
browser: playwright-cli -s=v3-retire headed chrome (not in-app browser)
```

### Baseline results
```text
Auth: richard maina on http://127.0.0.1:5173/units
In-app Cursor browser cannot complete Google OAuth; used external headed Chrome.
Old units left alone (Photosynthesis lesson 1 had a dead previous generation).

New unit created from UI:
- title: How Shadows Form
- unit_id: a5b9e24f-9c88-407b-bde3-71a9d27e3dd2
- lesson_1_id: 0fc47fa7-fd86-4e6e-9f58-e89d0eafe8fa
- generation_id: 913d086a-d1ef-4119-90f4-33e6aa0a08e1
- path: 2 lessons, locked in
- prepare → structural plan visible (orient/explain/contrast/check)
- Review concepts (structural approve) → 200
- status stage: awaiting_teaching_approval
- Teaching Plan visible with revision 1 + content hash
- Approve plan → Approved
- Create Learn → admitted, then Learn · failed
  (`shared task writer must return exactly one task per response-bearing block`)
- Create Print not yet started in this baseline walk
- Navigation has no /studio link in the primary sidebar
```

### Existing failures
```text
frontend/.env PUBLIC_API_URL=http://localhost:8001 caused Vite /api proxy ECONNREFUSED
and Internal Server Error on /api/v1/auth/google. Workaround: VITE_API_TARGET=http://127.0.0.1:8000
Plan page stayed on structural UI after approve until reload (teaching plan was already ready).
```

### Gate 0
- [x] PASS
- [ ] BLOCKED

---

## Phase A — Map

### Important discoveries
```text
<fill>
```

### Manifest changes
```text
<fill>
```

### Gate A
- [ ] all v3_execution production files classified
- [ ] all v3_blueprint production files classified
- [ ] all v3_studio routes classified
- [ ] all active frontend V3/Studio surfaces classified
- [ ] PASS

---

## Phase B — Extract

### B1 structured LLM/config
Files moved:
```text
<fill>
```
Tests:
```text
<fill>
```

### B2 item generation
Files moved:
```text
<fill>
```
Tests:
```text
<fill>
```

### B3 visual generation
Files moved:
```text
<fill>
```
Tests:
```text
<fill>
```

### Gate B
- [ ] current authoring no longer depends on v3_execution llm helpers
- [ ] current item pipeline uses new ownership
- [ ] current visual pipeline uses new ownership
- [ ] app startup passes
- [ ] targeted tests pass
- [ ] PASS

---

## Phase C — Planning move

Files moved:
```text
<fill>
```

Search evidence:
```text
<fill>
```

### Gate C
- [ ] Unit preparation has no current v3_blueprint import
- [ ] planning tests pass
- [ ] preparation/structural review proof passes
- [ ] PASS

---

## Phase D — Native API/UI extraction

Backend routes moved:
```text
application/unit_lesson/native_http.py
  lesson-approach get/approve/reject, realize-learn, realize-print,
  lectio-document get/put, page-block patch, visuals callback/retry, retry-native
application/unit_lesson/native_pipeline.py
  shared item generation + native teaching-plan halt
```

Frontend APIs/components moved:
```text
$lib/api/lesson-planning.ts, teaching-plan.ts, realizations.ts
StructuralPlanPreview / StructuralPlanActions
```

Temporary compatibility adapters:
```text
Chunked plan/status/approve/retry-section still registered on /api/v1/v3
because current clients call those URLs. Handlers call native_pipeline.
PDF export and document GET remain on the studio router.
```

### Gate D
- [x] current Unit Plan page no longer imports $lib/api/v3
- [x] native Teaching Plan / Learn / Print business logic no longer lives in the legacy router
- [ ] frontend tests/build pass (not re-run this pass)
- [x] app import passes; planning status tests 20 passed
- [ ] PASS (chunked HTTP adapters still on /api/v1/v3)

---

## Phase E — Backend legacy deletion

Deleted:
```text
section_writer, question_writer, answer_key_generator and their prompts
runtime runner, stage2_lanes, lanes, events, checkpoints, writer_schema,
lectio_validation, lesson_document
compile_orders, assembly builders
config concurrency/policy/answer_key_node
v3_review reviewer, card_reviewer, deterministic_checks
studio routes: /generate/start, /signals, /narrow, /propose-intent,
component patch, card repair, per-visual regenerate, traces, print-snapshot,
blueprint adjust
```

Zero-caller proof:
```text
rg of those modules under backend/src finds no production imports.
Remaining hits are node-name strings in model policy and timeout maps.
```

### Gate E
- [x] old section writer deleted
- [x] execute_section production references = 0
- [x] legacy Stage 2 generation start route removed
- [x] backend app import passes
- [x] tests/planning native status + pre-worker failure: 20 passed
- [ ] PASS (v3_blueprint compiler/models and studio chunked adapters remain)

---

## Phase F — Frontend legacy deletion

Deleted:
```text
routes/studio/+page.svelte and routes/studio/generations
V3 canvas, booklet, input, plan-preview components
$lib/api/v3.ts
```

Moved current components:
```text
Print editor stays at routes/studio/print/[id]
PDF download now uses $lib/api/realizations.downloadGenerationPdf
LectioPageDocumentView stays; unit Print and resource pages still render it
```

### Gate F
- [ ] current Unit/Learn/Print pages build
- [ ] no broken current navigation
- [ ] current Print viewer/editor works
- [ ] no unexplained active V3 components
- [ ] PASS

---

## Phase G — Namespace closeout

Search output summary:
```text
Current Learn/Print visual callers now import media.generation.contracts.
v3_execution.models re-exports those types so older tests keep one class identity.
Remaining production imports of v3_execution / v3_blueprint / v3_studio are the
live /api/v1/v3 router, persisted ProductionBlueprint, booklet status, and the
legacy stage-2 resume helper.
```

Remaining compatibility names and justification:
```text
/api/v1/v3 chunked plan, status, approve, document, PDF, pack routes
  — unit plan page and Print editor still call these URLs
ProductionBlueprint and BlueprintCompiler
  — persisted generation blueprint and preview DTO
v3_execution.booklet_status
  — generation writer still reads booklet status
resume_stage2 -> v3_blueprint.planning.retry
  — not called for new lessons; test_phase02_legacy_shutdown requires the helper to exist
frontend $lib/types/v3.ts and print/studio v3-* helpers
  — current Print document mapping, not the deleted Studio creation page
/studio/print/[id]
  — current Print editor
```

### Gate G
- [x] no unexplained v3_execution refs
- [x] no unexplained v3_blueprint refs
- [x] no unexplained v3_studio refs
- [x] no unexplained V3* active component names
- [x] PASS (adapters listed above)

---

## Phase H — E2E

Lesson/unit used:
```text
How Shadows Form / Light Travels in Straight Lines and Can Be Blocked
unit a5b9e24f-9c88-407b-bde3-71a9d27e3dd2
lesson 0fc47fa7-fd86-4e6e-9f58-e89d0eafe8fa
generation 913d086a-d1ef-4119-90f4-33e6aa0a08e1
```

Observed path:
```text
Units (logged in as richard maina)
 -> How Shadows Form (approved, 2 lessons, lesson 1 prepared)
 -> Open Lesson /plan
 -> Structural plan ✓ Teaching plan ✓ Approval ✓
 -> Teaching plan approved (revision 2, hash c530b26f…)
 -> Learn · failed: shared task writer must return exactly one task per response-bearing block
 -> Print · not created
```

Retries exercised:
```text
Retry Learn observed, not pressed
```

Negative legacy invocation proof:
```text
Open Lesson/Learn/Print hrefs are /units/.../plan|learn|print, not /studio?generation_id=
```

### Gate H
- [x] preparation
- [x] structural approval
- [x] Teaching Plan
- [x] Teaching Plan approval
- [ ] Learn
- [ ] Print
- [ ] visuals
- [ ] retry paths
- [x] final static searches
- [ ] PASS

---

## Blockers / decisions

For each blocker:

```text
Date:
Phase:
Observed:
Evidence:
Why it blocks:
Decision:
Files affected:
```

Do not silently invent an alternative architecture to bypass a blocker. Repair within the canonical architecture or document why the pack itself must be amended.

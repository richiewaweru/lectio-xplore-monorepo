# Whole-Lesson Native Path — Findings, Gaps & Design Recommendations

**Date:** 2026-08-05
**Branch:** `whole-lesson-native-e2e`
**Run under test:** `ebebdd9a-a14a-4f0e-9ac0-dd43bcc4f842` (Science G4 — "Why Light Is Essential for Food Making")

This documents the current state of the native whole-lesson pipeline as observed while driving
one real lesson through the browser, the concrete bugs found and fixed, the recurring failure
*patterns*, and the design changes worth exploring to make the path robust.

---

## 1. The path and where it actually stands

```
prepare ─▶ structural plan ─▶ APPROVE(struct) ─▶ item-gen ─▶ teaching plan ─▶ TEACHER GATE
   ✅            ✅                 ✅               ✅            ✅              ✅
        ─▶ APPROVE(teaching) ─▶ form plan ─▶ writers ─▶ assemble ─▶ persist ─▶ reload ─▶ render ─▶ PDF
                 code path          ⚠️          ⚠️         ⚠️         ⚠️         ⚠️        ⚠️      ⚠️
```

| Stage | Status | Evidence |
|---|---|---|
| prepare → structural plan | ✅ verified | native `document_contract_version=2`, skeleton orient→explain→contrast→check |
| APPROVE structural ("Review concepts") | ✅ verified | routes to native chunked approval, **no** Builder redirect |
| item generation | ✅ verified | stage2 item-gen completed, persisted |
| teaching plan (lesson-approach planner) | ✅ verified | real LLM plan, 4 sections, coherent arc (191s) |
| **teacher approval gate** | ✅ verified | halts at `awaiting_teaching_approval`; forms/writers do NOT run |
| APPROVE teaching → form plan | ⚠️ wired, unverified | code: `execute_after_teaching_approval` |
| writers → assemble → persist | ⚠️ wired, unverified | code path read, not yet exercised this run |
| reload from DB → render | ⚠️ unverified + gap | studio hydrates via legacy pack coercion; native v2 render likely needs the generation viewer |
| teacher/student PDF | ⚠️ unverified | `downloadV3GenerationPdf` exists; answer-visibility not yet checked for v2 |

**Bottom line:** the *front half* (prepare → teaching gate) is proven working on the real UI.
The *back half* (approve → … → PDF) is wired in code but not yet exercised end-to-end, and has at
least two known structural weaknesses (below).

---

## 2. Concrete bugs found & fixed (each with a regression test)

1. **Prepare 422 — ConceptCard extras.** `bridge.py` did not strip planner-emitted
   `misconceptions[*].rationale` and a top-level `concept_id`; the strict `ConceptCard`
   (`extra="forbid"`) rejected them. Fixed by filtering both to their allowed keys.
2. **Char limits hard-failing generation.** `LessonIntent.goal` (and `AnchorSpec`, `SectionPlan`
   titles/notes) had `max_length` caps; a long compound objective 422'd prepare. Per direction,
   these are now **advisory** (caps removed; list-size limit kept).
3. **Native-gate DTO type drift.** Frontend `V3StructuralPlan` never declared
   `document_contract_version`, so the native branch read an undeclared field. Declared it +
   added a regression test that the native (dcv=2) path routes through chunked approval, not Builder.
4. **Frontend native post-approval blindspot.** No handling for `planning_forms`/`generating`
   stages → resume showed a blank screen. Added rendering + polling + a regression test.

---

## 3. Recurring failure *patterns* (the real story)

These four patterns account for essentially every problem hit. Each is a class, not a one-off.

### Pattern A — Strict contracts vs. LLM output drift  →  hard 422s
Planner models use `extra="forbid"` + `max_length`. Benign LLM variance (an extra `rationale`,
a `concept_id`, an objective one clause too long) turns into a **generation-killing** validation
error at an internal boundary. We've now patched three instances by hand.

### Pattern B — Long work runs *inside the HTTP request*  →  stalls on disconnect
`POST …/lesson-approach/approve` runs form-plan + all writers + assembly **synchronously** (5–15
min). If the client/proxy drops that request, uvicorn cancels the task mid-flight and the
generation is left stranded. This is exactly the state the *previous* generation
(`890c7cb8`) is stuck in: `planning_forms`, no document.

### Pattern C — Failure state not persisted  →  UI hangs forever
When native stage2 failed (a transient LLM connection error), the error handler's
`stage2_error` write **did not land** — the DB still showed `stage2_running`, `error=null`. The
UI therefore polled forever on "Writing your resource…" with no way to surface or recover the
failure. (The teaching planner itself was fine on retry; the *hang* was this bug.)

### Pattern D — Transient provider connection resets  →  whole stage dies after 2 quick tries
The lesson-approach call (`deepseek-v4-pro`, `reasoning=high`, large prompt) hit
`APIConnectionError: Connection error.` The retry loop does 2 back-to-back attempts with **no
backoff**, so a short provider blip fails both. A direct re-run succeeded in 191s — so it was
transient, but the current policy has no cushion for it.

### (Cross-cutting) Split source-of-truth for "stage"
Completion/stage lives in three places — `generation.status`, `chunked_state.stage`, and the
page-document store — and they drift. After execution the executor sets
`generation.status="completed"` but leaves `chunked_state.stage="planning_forms"`; completion is
only detectable via the persisted document. This is what makes the frontend state machine brittle.

---

## 4. What's missing to make the path complete

- **Back-half execution proven + made robust** (Pattern B): background the post-approval run.
- **Native document render surface**: studio's `coerceV3DocumentToPack` targets the *legacy* pack;
  native `LectioDocumentV2` should render through the generation viewer / `@lectio/page`.
- **PDF export for v2** with correct teacher/student answer visibility (verify + wire).
- **Terminal stage write** in the executor (set `chunked_state.stage="complete"` + emit event).
- **Reliable failure-state persistence** so any stage failure is recoverable from the UI.
- **Transient-error retry policy** (backoff + jitter) distinct from validation-repair retries.

---

## 5. Design to explore (recommended, prioritized)

**P0 — Coercion boundary for planner output (fixes Pattern A permanently).**
Introduce one adapter layer that maps *raw planner JSON* → *strict contract*, doing all
normalization (drop unknown keys, treat length as advisory, coerce enums, map synonyms) in a
single well-tested place, instead of scattering `_normalize_*` helpers. Strict models stay strict
internally; the LLM boundary is lenient-by-design. Net effect: LLM variance never 422s a run.

**P0 — Background the post-approval execution (fixes Pattern B).**
Split `approve_teaching_and_execute`: (a) in-request → record approval, set stage, return 202;
(b) background task (own DB session, same pattern as `_run_chunked_stage2_pipeline`) → form-plan →
writers → assemble → persist → set terminal stage + emit event. The frontend (already taught to
handle `planning_forms`/`generating`) polls to completion. Removes the 5–15 min fragile request
and the stall class entirely.

**P1 — Single stage state-machine + reliable failure writes (fixes Pattern C + drift).**
One authoritative `stage` with a defined transition set incl. terminal `complete`/`failed`. Every
pipeline exit (success or exception) writes it atomically; the executor updates it on completion.
Investigate why the current `except`-block `persist_chunked_state` didn't land (likely session/
ordering) and make failure persistence a guaranteed finally-step.

**P1 — Transient-vs-permanent retry policy (fixes Pattern D).**
Classify transport errors (`APIConnectionError`, read timeouts) separately from schema/validation
failures. Transport → N attempts with exponential backoff + jitter; validation → the existing
single repair attempt. Apply uniformly via the shared `run_llm` runner so every planner benefits.

**P2 — Native-path frontend surface.**
A dedicated native progress view (not the legacy per-section "brief canvas", which shows empty
`{}` and is misleading), and native `LectioDocumentV2` rendering via the generation viewer. Keep
the legacy stage2 canvas for the legacy path only.

**P2 — Dev-loop friction.**
Proof runs require backend without `--reload`; every backend fix needs a manual restart. Consider
a proof profile that reloads on non-request-critical changes, or a documented one-command restart.

---

## 6. Suggested next action

Two viable next steps, pick per priority:
- **Prove the back half now** (answers "is the rest wired"): run the real approve→execute for
  `ebebdd9a…` and confirm a reloaded `LectioDocumentV2` + differing teacher/student PDFs. Fastest
  path to a complete Run-1 gate signal; will likely surface the render/PDF gaps to fix.
- **Fix the patterns first** (P0 items) then re-run clean: durable, but slower to a first PDF.

Recommendation: do the P0 **background-execution** change and the **coercion boundary** as they
directly unblock and de-risk everything downstream, then complete Run 01 on top of them.

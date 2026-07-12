# INVESTIGATION — v3 document polling + truthful canvas (2026-07-12)

Branch: `v3`. Follow-up to Codex commits `26c4be7`, `50840b5`.

## Phase 0 — Findings

Railway CLI is not available in this environment, so Phase 0 was done by static
verification against the real code paths (grep + full read of the pump, writer,
runner, and studio frontend). Both hypotheses from the handoff were confirmed
in code:

### H1 confirmed — generation task not durable, no terminal stage → infinite poll

- `_pump_sse_to_queue` was spawned via fire-and-forget `asyncio.create_task(...)`
  at both call sites (`/generate/start` and the chunked start path) with **no
  retained reference** — eligible for GC mid-run.
- The pump's `async for` was wrapped in `except Exception: pass` — any crash was
  silently swallowed, no terminal snapshot written, `progress.stage` stayed
  non-terminal, frontend polled `/document` forever.
- A Railway restart/redeploy mid-run kills the process; nothing marked the row
  terminal on the next boot, so those runs also polled forever.
- `50840b5` only covers terminal-status-with-no-snapshot; it does not cover a
  silently dead task (no terminal status is ever reached).

### H2 confirmed — snapshot missed incremental content → canvas not truthful

- `_write_generation_snapshot` only persisted pack-level events
  (`skeleton_ready`, `section_ready`, `draft_pack_ready`, `draft_status_updated`,
  `final_pack_ready` + progress-only events).
- `component_ready`, `question_ready`, `visual_ready`, `component_patched`
  (emitted by `section_writer.py`, `question_writer.py`, `visual_executor.py`)
  were never written to `document_json`. With SSE demoted to a poke, that content
  reached nobody until a section fully completed (`section_ready` fires only when
  a section's components AND questions AND visuals are all done — runner.py
  `_emit_ready_sections`). Canvas sat on the skeleton for most of the run.

## Fix

### Phase 1 — durable pump, always-terminal (backend)

`backend/src/generation/v3_studio/router.py`:
- Pump/background tasks are retained in module-level `_background_tasks` with a
  done-callback that discards and **logs** any swallowed exception.
- The pump tracks whether a terminal event (`resource_finalised` /
  `generation_warning`) was seen. On ANY other exit — exception, cancellation,
  or the stream ending silently — it writes a terminal failure snapshot
  (`progress.stage = "failed"` + `write_failure`, error_type
  `generation_pump_failure`) via a retained background task, so it lands even
  when the pump itself is cancelled.
- Exceptions are now logged loudly instead of `pass`.

`backend/src/generation/v3_studio/generation_writer.py` + `backend/src/app.py`:
- `fail_stale_running()`: on startup (single uvicorn worker per railway.toml),
  any v3 generation still `status="running"` belongs to a process that died —
  it is marked failed (`error_type="server_restart"`, stage `failed`). This is
  what makes a Railway redeploy mid-run stop the frontend poll.

### Phase 2 — truthful snapshot (backend + frontend test)

- `V3GenerationWriter.merge_stream_event()` merges `component_ready`,
  `component_patched`, `question_ready`, `visual_ready` into the matching
  section of `document_json`, mirroring the frontend merge semantics
  (`mergeComponentField`, `mergePracticeProblem`, `mergeDiagramFrame` in
  `v3-canvas.ts`), and bumps `progress.sections[section_id]` to `writing`.
  Failed visuals and unknown sections are ignored (partial = partial, silently).
- `_write_generation_snapshot` dispatches those four event types to the merge.
- Frontend: no code change needed — `mapPackSectionsToCanvas` already renders
  section dicts as `mergedFields`; `page.test.ts` extended to prove a partial
  `explanation` body from a polled snapshot reaches the canvas.

## Tests (all green)

- `backend/tests/generation/test_v3_pump_durability.py` (new): crash mid-stream
  → stage `failed`; silent stream end → `failed`; cancellation → `failed`;
  normal terminal → NOT failed; component/question/visual merged into
  `/document` before `draft_pack_ready` even when the run dies.
- `backend/tests/generation/test_v3_generation_writer.py`: merge semantics +
  stale-running sweep.
- `uv run pytest tests/generation` → 100 passed. `ruff` clean. Architecture
  guard clean. `npm run test` (studio) 54 passed, `npm run check` 0 errors.

## Phase 3 — live verification (2026-07-12, Railway deploy `1154756`)

Deployed service: `text-book-generator Copy Copy` on Railway (deploys `v3` via
GitHub; deployment of `1154756` confirmed successful in the dashboard).
Frontend: https://text-book-v3.vercel.app.

- **Exit ticket run `a234d2cb` (Grade 6, adding like fractions):** executed
  end-to-end. `GET /document` returned the section with populated component
  bodies (`short_answer`, `fill_in_blank`, `student_textbox`) — the polled
  snapshot carries real content, not an empty shell. The run landed on a
  terminal `progress.stage` (`failed`, because the coherence review rejected
  the draft → `draft_needs_review` / `failed_finalisation`); the studio stopped
  polling, moved to the edit state, rendered the full draft on the canvas, and
  offered "Download Draft PDF (Review Needed)". No infinite poll.
- **Earlier lesson runs `d1461afd`, `b28b64dd`:** both reached terminal
  `status=partial` on their own — no stuck-forever generations in the DB.
- **Observed (pre-existing, planning-side, NOT fixed here):**
  1. Stage-2 planning went `assembly_blocked` once with an empty
     `failed_sections` list, and the frontend kept showing "Writing your
     resource…" because only the stage-2 SSE stream carries that state —
     the chunked-status poll path doesn't surface it. Same "silent death"
     class of bug as H1 but in the planning stage.
  2. On resume of an `assembly_blocked` generation, the plan renders read-only
     with no retry/approve control (dead-end UI); re-POSTing `/chunked/{id}/approve`
     un-blocks it.
  3. Exit-ticket coherence review flags "expected 3 practice questions, found 0"
     while the questions are clearly rendered as components — planned questions
     are "not consumed" by assembly for this template, so small resources
     terminate as `draft_needs_review` even when the content looks right.
- **Kill-test (worker restart mid-run):** covered by the regression tests and
  the startup sweep; live restart pending (requires restarting the production
  Railway service mid-generation).

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

## Phase 3 — live verification

- Pending: in-browser run against the deployed app (canvas fills progressively,
  polling stops at completion; redeploy mid-run lands `failed`, no infinite
  poll). To be recorded here after deploy of this branch.

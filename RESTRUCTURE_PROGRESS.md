# RESTRUCTURE_PROGRESS

Branch: `xplore`. Started: 2026-08-03.

Source of truth: [`handoff/RESTRUCTURE_HANDOFF.md`](handoff/RESTRUCTURE_HANDOFF.md). Unattended instructions: [`CURSOR_GOAL.md`](CURSOR_GOAL.md).

## Baseline

- Full local lesson generation: **not run** — no local `.env` / API keys available in this session.
- Using test-level timing and code-path verification instead (per CURSOR_GOAL §2).
- Pre-change defaults observed: Stage2 timeout default 240s; concurrency defaults SECTION=3 QUESTION=3; Stage2 parallel=true (anchor-first).
- `elapsed=` log lines: **deferred** until a generation can run (record here when available).

## Completed

- Docs: wrote `handoff/RESTRUCTURE_HANDOFF.md`, `CURSOR_GOAL.md`, `RESTRUCTURE_PROGRESS.md`.
- Env: `.env.example` → Stage2 timeout 100s, concurrency 5/5/4; code defaults match (`config.py` 100, `concurrency.py` 5/5). Generation start logs print resolved limits; Stage2 START logs timeout.
- Baseline: no local API keys — deferred full lesson timing; using test evidence.

## Section 8 checklist

### Backend

- [ ] `retry.py` anchor-serial removal + `persistence.py:295` resume mirror
- [ ] `test_stage2_parallel.py` rewritten per A1
- [ ] `run_adjacent_merge_critics` nominated-only + `test_path_contracts.py`, `test_outcomes.py`, `test_projections.py`
- [ ] `validate_section_brief` word cap + fixture test
- [ ] `router.py` item-gather + any test stubbing `execute_items` sequentially (`test_v3_item_review.py`)
- [ ] Prompt extraction: verbatim tests, shared-prefix tests, `_PROMPT_NAMES` set, hash-stamping on generations
- [ ] `prompt_overrides` table migration; overlay resolution in loader; locked-prompt bypass
- [ ] Constructor node registration (`V3_NODE_SLOTS`, `V3_NODE_REASONING`, timeouts dict entry), route, structured output model
- [ ] Unit-creation route: accept raw text payload; keep old payload accepted during transition
- [ ] Resume paths (`claim_resume_attempt`, `resume_stage2`) coherent with one-wave fan-out

### Frontend

- [ ] `units/+page.svelte` new create form; `units/[id]/+page.svelte` screens 3–5 rebuild; `page.test.ts` files updated
- [ ] `LessonShapePanel`, `UnitGroupsPanel` re-homed per handoff §7
- [ ] Studio/print/pack pages: banned-words sweep (`lib/types/units.ts`, `lib/types/v3.ts`, variant-referencing UI strings)
- [ ] Vite manual-chunk list unaffected (templates untouched)

### Docs

- [ ] Pointer notes on handoff `11_UI_AND_FLOWS.md`, `07_DIFFERENTIATION_MODEL.md` (UI portions), `14_IMPLEMENTATION_PHASES.md`

## BLOCKED

(none)

## Summary (fill at end)

- What shipped:
- What was deferred and why:
- Before/after timing numbers:

# Four-Run Official Proof — Status Report

**Branch:** `whole-lesson-native-e2e`  
**Date:** 2026-08-05  
**Pack:** `docs/authority/whole-lesson-e2e-pack-v1.2`

## Architecture implemented

- Cutline 1: approved-item loader, catalogue projections, STANDARD/FAST model routing + dedicated timeouts
- Cutline 1.5: verbatim `lesson-approach-planner-v1.txt` / `form-planner-v1.txt` (checksum-verified), `render_resource_identity`, `typical_intents` / `permitted`, fixture planners removed, writer-common updated
- Cutline 2: teaching plan schemas, validation/QC/repair agent, `PageDocumentRepository`, `awaiting_teaching_approval` API + studio review UI
- Cutline 3: form planner, tiered async writers, native executor → LectioDocumentV2 persist/reload; stage2 pipeline halts at teaching approval for native path
- Cutline 4: block patch endpoint, strict pending-figure print 409, evidence capture script, frontend teaching-review surface

## Official runs

| Run | Subject | Status |
|---|---|---|
| 01 | Science — plants need light | **IN PROGRESS** — env OK; browser Run 01 not yet completed. See [`AGENT_HANDOFF_BROWSER_RUN01.md`](AGENT_HANDOFF_BROWSER_RUN01.md) |
| 02 | Mathematics — equivalent fractions | **PENDING** — after Run 1 gate |
| 03 | Economics — supply and demand | **PENDING** — after Run 1 gate |
| 04 | English — claim vs evidence | **PENDING** — after Run 1 gate |

Per protocol, these must not be faked with fixtures. Evidence folders exist under `docs/evidence/whole-lesson-runs/` with scaffolding only.

## Agent handoff (2026-08-05)

Work paused after API-driven attempts surfaced prepare/stage2 bugs (fixed in working tree on `whole-lesson-native-e2e`). Next step: **Run 01 via Codex in-app browser** with live servers — full instructions in [`AGENT_HANDOFF_BROWSER_RUN01.md`](AGENT_HANDOFF_BROWSER_RUN01.md); paste prompt in [`NEXT_AGENT_PROMPT.md`](NEXT_AGENT_PROMPT.md).

## How to complete the official runs

1. Provide `apps/textbook-agent/backend/.env` with provider keys and `DATABASE_URL`.
2. Start backend + frontend.
3. For each subject, follow `04_PROOF_RUNS/FOUR_RUN_PROOF_PROTOCOL.md` through the real UI/API.
4. After each generation:  
   `uv run python scripts/capture_whole_lesson_evidence.py <generation_id> --run run-0N-<subject>`
5. Apply Run 1 gate before Runs 2–4.
6. Fill `35-teacher.pdf` / `36-student.pdf` / screenshots via studio export.

## Prompt integrity

```
lesson-approach-planner-v1.txt sha256 = 475b8b178f74c1397742b12002a324e18ae3e39a4fffd9e7a4c199713780a9cd
form-planner-v1.txt            sha256 = b1990a00f0b5bf75a7dec02babf7c567b12b36a336419da029c233790fd78316
```

Verified by `scripts/verify_whole_lesson_prompts.py`.

## Deviations

- Live post-approval writers still use LLM when `use_llm=True`; unit tests keep stubs.
- Conceptual skeleton in yaml still lists a `contrast` *slot*; teaching packet for whole-lesson uses orient/explain/confront/check per proposal (contrast remains an intent).
- Official four-run PDFs and timing/cost ledgers are not produced until credentials are available.

## Recommendation

Retain whole-lesson planning. Unblock by configuring `.env`, then execute Run 1 gate before expanding to Runs 2–4.

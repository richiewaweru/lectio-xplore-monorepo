# Agent Handoff — Whole-Lesson Native E2E (Browser-First, Run 01 Minimum)

**Date:** 2026-08-05  
**Branch:** `whole-lesson-native-e2e` (from `pageobject-integration`)  
**Repo:** `C:\Projects\lectio` (lectio-xplore monorepo)  
**Paste-ready prompt for next session:** [`NEXT_AGENT_PROMPT.md`](NEXT_AGENT_PROMPT.md)  
**Immediate goal:** Get **one** official lesson working end-to-end through **Codex's in-app browser** (real Xplore UI at `http://localhost:5173`) — Run 01 Science — then capture evidence. Do **not** fake with fixtures. Four-run comparison can wait until Run 01 gate passes.

---

## 1. What we are building

**Whole-lesson native planning** replaces per-section fixture planners with:

1. **Lesson packet** (immutable inputs from path + approved items)
2. **Teaching plan** (single lesson-approach LLM call) → **teacher approval gate**
3. **Form plan** (form planner LLM call)
4. **Tiered block writers** → **LectioDocumentV2** persist/reload
5. Teacher + student PDF export

Authority pack (read first):

- `docs/authority/whole-lesson-e2e-pack-v1.2/00_READ_ME_FIRST.md`
- `docs/authority/whole-lesson-e2e-pack-v1.2/04_PROOF_RUNS/FOUR_RUN_PROOF_PROTOCOL.md`
- Architecture: `docs/authority/whole-lesson-e2e-pack-v1.2/01_ARCHITECTURE/xplore-whole-lesson-planning-resolved-proposal-v1.1.md`

**Run 01 concept:** Science, Grade 4 — *Why plants need light to make food*  
Skeleton: **orient → explain → confront → check** (`lesson_mode: first_exposure`, conceptual).

Evidence output folder: `docs/evidence/whole-lesson-runs/run-01-science/`

---

## 2. Monorepo structure (what lives where)

```
C:\Projects\lectio\
├── apps/textbook-agent/          # Xplore app (backend + frontend)
│   ├── backend/
│   │   ├── .env                  # secrets — gitignored, already copied from Textbook agent
│   │   ├── .env.example          # safe template
│   │   ├── src/
│   │   │   ├── core/             # config, auth, DB, shared infra
│   │   │   ├── planning/         # units, path, bridge, whole_lesson/*
│   │   │   ├── generation/       # v3 studio router, page_objects
│   │   │   └── pipeline/         # must NOT import planning/generation
│   │   ├── resources/            # LLM prompts (byte-identical to authority pack)
│   │   └── scripts/
│   │       ├── verify_whole_lesson_prompts.py
│   │       ├── capture_whole_lesson_evidence.py
│   │       └── run_whole_lesson_proof.py   # API driver (optional; browser preferred)
│   └── frontend/
│       ├── .env                  # VITE_GOOGLE_CLIENT_ID, PUBLIC_API_URL
│       └── src/routes/
│           ├── units/            # create unit, path plan, prepare lesson
│           └── studio/           # chunked review, teaching approval, generation view
├── docs/
│   ├── authority/whole-lesson-e2e-pack-v1.2/   # spec + protocol
│   └── evidence/whole-lesson-runs/             # proof artifacts
└── packages/lectio-page/         # @lectio/page render contracts
```

**Canonical routes:**

- Units / path: `/units` → unit detail → path plan → approve → prepare lesson
- Studio after prepare: `/studio?generation_id=<uuid>`
- Generation view: `/textbook/[id]` (maps to generation ID)

**Architecture rules:** See `apps/textbook-agent/CLAUDE.md` and `agents/ENTRY.md`. Pipeline never imports planning/generation.

---

## 3. What is already done (Cutlines 1–4)

| Cutline | Delivered |
|---|---|
| 1 | Approved items loader, catalogue projections, model tiers, page timeouts in config |
| 1.5 | Verbatim teaching/form prompts; fixture section planner removed; `typical_intents` |
| 2 | Teaching plan agent/validation/QC; `PageDocumentRepository`; `awaiting_teaching_approval` API + Studio UI |
| 3 | Form planner, writers, native executor, LectioDocumentV2 persist |
| 4 | Block patch, strict figure print 409, evidence capture script, teaching review UI |

**Env:** `apps/textbook-agent/backend/.env` and frontend `.env` copied from `C:\Projects\Textbook agent` with monorepo overrides (`LECTIO_CONTRACTS_DIR=./contracts`, `FRONTEND_ORIGIN` / PDF at `:5173`). `.env` is gitignored.

**Prompt checksums (must stay byte-identical):**

```
lesson-approach-planner-v1.txt  sha256=475b8b178f74c1397742b12002a324e18ae3e39a4fffd9e7a4c199713780a9cd
form-planner-v1.txt             sha256=b1990a00f0b5bf75a7dec02babf7c567b12b36a336419da029c233790fd78316
```

Verify: `cd apps/textbook-agent/backend && uv run python scripts/verify_whole_lesson_prompts.py`

---

## 4. Bugs fixed in working tree (uncommitted — verify before run)

Previous API-driven attempts hit these; fixes are in the branch working tree:

| Issue | Symptom | Fix location |
|---|---|---|
| Legacy components on native path | Prepare 422: `SectionPlan` wants `slug`/`purpose`, got `type: hook-hero` | `planning/bridge.py` — clear `components`/`blocks` when `page_block_plans is not None` |
| Page structural planner card shape | Prepare 422: `ConceptCard` missing `objective`, extra `definition` | `planning/bridge.py` — `_normalize_page_concept_card_payload()` |
| Wrong structural prompt on native path | Planner emits legacy shapes | `planning/agents.py` — use `path_structural_planner_page_prompt()` when `native_whole_lesson` |
| Async chunked state bug | Stage2 error: `'coroutine' object has no attribute 'get'` | `planning/whole_lesson/repository.py` — `await load_chunked_state(id, session)`; correct `persist_chunked_state` args |
| Same async bug in service | Teaching plan crash on first event | `planning/whole_lesson/service.py` — await `load_chunked_state(generation.id, session)` |

**Run backend without `--reload` during long LLM calls** — reload mid-request caused 500s and lost work.

Optional API driver (not required for browser path): `backend/scripts/run_whole_lesson_proof.py`

---

## 5. Start servers (do this first)

```powershell
# Terminal 1 — backend (NO --reload for proof runs)
cd C:\Projects\lectio\apps\textbook-agent\backend
uv sync --all-extras   # once
uv run uvicorn app:app --host 127.0.0.1 --port 8000

# Terminal 2 — frontend
cd C:\Projects\lectio\apps\textbook-agent\frontend
npm ci                 # once
npm run dev
# Open http://localhost:5173  (use localhost, not 127.0.0.1, for Google OAuth)
```

**Preflight checks:**

```powershell
curl http://127.0.0.1:8000/health
curl http://localhost:5173
cd C:\Projects\lectio\apps\textbook-agent\backend
uv run python scripts/verify_whole_lesson_prompts.py
```

**Required env flags (already in `.env`):**

- `XPLORE_V2_ENABLED=true`
- `XPLORE_PAGE_DOCUMENTS_ENABLED=true`
- `XPLORE_PAGE_DOCUMENT_SCOPE=conceptual_first_exposure`
- `DATABASE_URL` — Railway Postgres (remote) or local docker `db-dev`
- `GOOGLE_CLIENT_ID` + frontend `VITE_GOOGLE_CLIENT_ID` — same OAuth client; origins must include `http://localhost:5173`
- Provider keys: `DEEPSEEK_API_KEY`, etc. (V3 slots map to DeepSeek in copied env)

---

## 6. Browser workflow — Run 01 Science (step by step)

Use **Codex's in-app browser** at `http://localhost:5173`. Sign in with Google when prompted (OAuth cannot be fully scripted).

### Phase A — Unit and path

1. Go to **`/units`** → create unit:
   - **Title:** Why Plants Need Light to Make Food
   - **Topic:** Why plants need light to make food
   - **Subject:** Science
   - **Grade:** Grade 4
   - **Destination objective:** Explain why plants need light to make food.
   - **Starting knowledge:** plants have roots/stems/leaves; living things need food to grow

2. **Plan path** (real path planner — ~2–5 min). Wait for completion.

3. If **open assumptions** appear, resolve each (mark as known/teach as appropriate).

4. **Approve path.**

5. Pick a **conceptual** lesson whose objective best matches *plants need light* / photosynthesis / making food — not a tangential prerequisite lesson.

6. **Prepare lesson** with `first_exposure` mode. Note the **`generation_id`** from URL redirect to Studio (`/studio?generation_id=...`).

### Phase B — Structural review → teaching plan

7. In **Studio**, review structural plan if prompted → **Approve** chunked plan (starts stage2).

8. Wait for stage **`awaiting_teaching_approval`** (can take **5–15 min**: item generation + lesson-approach planner). UI shows teaching review.

9. **Review teaching plan** (protocol order):
   - Last block brief **first**
   - Then first brief, arc, intents, evidence refs, anchor, misconceptions, check items

10. **Approve teaching plan** in UI (do not auto-approve via script for this handoff).

### Phase C — Writers → document → PDFs

11. After approval, wait for form plan + writers + document **complete** (another **5–15 min**).

12. Open generation page; confirm **LectioDocumentV2** renders in viewer.

13. Export **teacher PDF** (`include answers`) and **student PDF** (no answers). Save as:
    - `docs/evidence/whole-lesson-runs/run-01-science/35-teacher.pdf`
    - `docs/evidence/whole-lesson-runs/run-01-science/36-student.pdf`

14. Screenshot generation page → `34-generation-page.png`

### Phase D — Evidence capture

15. From backend:

```powershell
cd C:\Projects\lectio\apps\textbook-agent\backend
uv run python scripts/capture_whole_lesson_evidence.py <generation_id> --run run-01-science
```

16. Manually fill templates (copy from `_templates/`):
    - `33-quality-scorecard.md`
    - `32-input-output-trace.md`
    - `00-manifest.yaml` (use `RUN_MANIFEST_TEMPLATE.yaml`)
    - `39-conclusion.md`

17. Apply **Run 1 gate** (protocol §10) before starting Runs 02–04:
    - Final brief not materially weaker than first
    - No page-object IDs in teaching prompt/plan
    - Teacher approval genuinely blocked downstream until approve
    - Document persisted **and** reloaded (`30-reloaded-lectio-document.json`)
    - Teacher vs student PDFs differ on answer visibility
    - No fixture/legacy conversion

---

## 7. Expected timing (one lesson)

| Stage | Wall clock |
|---|---|
| Path plan | 2–5 min |
| Prepare (structural planner) | 1–3 min |
| Stage2 → teaching plan | 5–10 min |
| Approve → form + writers | 5–15 min |
| PDFs + capture | 2–5 min |
| **Total** | **~15–35 min** |

Failures during LLM calls are normal; retry from last stable step. Do not commit `.env`.

---

## 8. Key code paths (for debugging)

| Step | Code |
|---|---|
| Path prepare + native flag | `planning/bridge.py` → `prepare_path_lesson`, `initialise_path_generation` |
| Stage2 halt | `generation/v3_studio/router.py` → `_run_chunked_stage2_pipeline` (native branch) |
| Teaching plan | `planning/whole_lesson/service.py` → `run_and_persist_teaching_plan` |
| Teacher approve | `POST /api/v1/v3/generations/{id}/lesson-approach/approve` |
| Post-approve execution | `planning/whole_lesson/service.py` → `approve_teaching_and_execute` |
| Persistence | `planning/whole_lesson/repository.py` (`page_document_v2` in chunked state) |
| Studio UI | `frontend/src/routes/studio/+page.svelte` |
| API helpers | `frontend/src/lib/api/units.ts`, `frontend/src/lib/api/v3.ts` |

**Native path gate:** `XPLORE_PAGE_DOCUMENTS_ENABLED` + conceptual + `first_exposure` → `native_whole_lesson: true` in chunked context.

---

## 9. Hard failures (protocol §11 — run fails if any occur)

- Fixture planning or placeholder writing
- Form/writers start before teacher approval
- Invented question IDs or content
- Document rendered without reload from DB
- Missing raw prompts/responses in evidence
- Teacher and student PDFs identical when answer key exists

---

## 10. Current status (as of handoff)

| Item | Status |
|---|---|
| Architecture Cutlines 1–4 | Implemented |
| `.env` / DB / prompts | Configured and verified |
| Official Run 01 evidence | **Not complete** — multiple API attempts failed on bugs now fixed in working tree |
| Runs 02–04 | Not started (blocked on Run 1 gate) |
| `FOUR_RUN_REPORT.md` | Still shows old “BLOCKED on .env” — update after Run 01 succeeds |

**Success criterion for next agent:** One complete `run-01-science/` folder with teaching + form artifacts, reloaded document JSON, teacher/student PDFs, scorecard, and Run 1 gate passed — all via **browser + capture script**, no fixtures.

---

## 11. After Run 01 works

1. Update `docs/evidence/whole-lesson-runs/FOUR_RUN_REPORT.md`
2. Repeat browser flow for Runs 02–04 (Math, Economics, English) only if Run 1 gate passes
3. Consider committing code fixes (not `.env`) on `whole-lesson-native-e2e`

---

## 12. Quick reference commands

```powershell
# Prompt integrity
cd C:\Projects\lectio\apps\textbook-agent\backend
uv run python scripts/verify_whole_lesson_prompts.py

# Capture after browser run
uv run python scripts/capture_whole_lesson_evidence.py <generation_id> --run run-01-science

# Focused tests (before burning LLM time)
uv run pytest tests/planning/test_whole_lesson_smoke.py tests/planning/test_teaching_validation.py -q

# Architecture guard
cd C:\Projects\lectio\apps\textbook-agent
uv run python tools/agent/check_architecture.py --format text
```

**Do not edit** prompt files under `backend/resources/lesson-approach-planner-v1.txt` or `form-planner-v1.txt` without recording a new prompt version in evidence.

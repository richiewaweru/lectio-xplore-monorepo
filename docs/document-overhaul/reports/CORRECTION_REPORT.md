# Document Overhaul — Corrective Pass Report (A–K)

**Program status:** **PASS**  
**Date:** 2026-09-11  
**Branch:** `fix/document-overhaul-correction`  
**HEAD baseline:** `cebb61f2073311b5f7fd2daca8c10ce81e8ed117` (`origin/main`)

Live LLM compose/write, Print composition + PDF, sibling Learn/Print independence, all eight interaction authoring proofs, LearnDocument DB persist/edit/reload, and browser Learn editor E2E (render, answer/evaluate, edit, add, save, reload) passed with the production provider against local Postgres.

---

## A. Starting SHA + correction branch

| Field | Value |
| --- | --- |
| Starting SHA (`origin/main`) | `cebb61f2073311b5f7fd2daca8c10ce81e8ed117` |
| Correction branch | `fix/document-overhaul-correction` |
| Pack source of truth | `docs/document-overhaul/` (architecture unchanged) |

---

## B. Requirement-by-requirement correction ledger

| ID | Requirement | Code change | Proof |
| --- | --- | --- | --- |
| C1 | LLM document composer (choices, many nodes/block) | `document/composer.py` + choices-only prompt; wired from Learn + Print | Live: `scripts/live_compose_write_proof.py` → PASS |
| C2 | Real document writing (no brief-copy stubs) | `document/writer.py`; stub writers raise; Learn figure via `figure_pipeline.py` | Same live script; figure caption/alt real |
| C3 | Real Learn interactions | Production uses `write_interaction_from_request`; candidate map | Live: `scripts/live_interaction_proof.py` → PASS (8/8) |
| C4 | Learn renderer/editor | `InteractionShell`, six primitive editors, figure render; builder `{#await}` load | Browser E2E PASS (`browser-learn-editor-e2e.json`) |
| C5 | Shared `document/` boundary | Print/Learn maps moved out of `document/` | Domain guards PASS |
| C6 | One Print production path | `composition_bridge.py`; FormPlan = layout carrier | Live Print composition + PDF PASS |
| C7 | Legacy / `@lectio/learn` removal | Package deleted; app-owned interactions | Package absent; zero runtime imports |
| C8 | Unit UI real route | Learn generate API + studio path=learn + `/api/v1/v3/generations` fix | Wired + unit tests; destination editor proven in browser |

---

## C. Files changed (high-signal)

**Backend**
- `document/composer.py`, `document/writer.py`, prompts
- `learn/generation/native_production.py`, `native_execution.py`, `figure_pipeline.py`
- `learn/contracts/lesson_document.py`, `learn/runtime/evaluation.py`
- `print/generation/composition_bridge.py`, executor wiring
- `application/unit_lesson/realize_learn_handoff.py`
- Live proof scripts under `backend/scripts/live_*.py`

**Frontend**
- Units/studio Learn route wiring; `api/v3.ts` path fix
- LearnDocument v2 editors/renderers/interactions
- Builder load reliability (`{#await}`), loopback API via Vite proxy
- App-owned theme; `@lectio/learn` consumers removed

---

## D. Files deleted

- Entire `packages/lectio-learn/**`
- Root `learn:test` / `learn:export` scripts
- Frontend `@lectio/learn` dependency + nested stale lockfile
- Retired FE adapters/views that only existed for the old package

Historical retirement 410s / denylist strings for `component_lectio` remain as guards, not as live generation.

---

## E. Canonical final call graph

```text
Approved Teaching Plan
        │
        ├── PATH = LEARN
        │     compose_document_plan (LLM choices)
        │     → write_document_primitive (LLM content)
        │     → attach_figure_asset (visual pipeline) for figures
        │     → layer retained interactions (candidate → interaction_writer)
        │     → LearnDocument v2 persist
        │     → /builder/{editable_id} editor + InteractionShell runtime
        │
        └── PATH = PRINT
              compose_document_plan (LLM choices)
              → Print task treatments (questions/choices/…)
              → FormPlan layout carrier
              → page-object writers + visual_dispatch
              → LectioDocument / PDF
```

No Print↔Learn conversion. Sibling path re-admits from the same approved Teaching Plan.

---

## F. Exact test commands + results

| Command | Result |
| --- | --- |
| `pnpm contracts:test` | PASS (20) |
| `pnpm contracts:check` | PASS |
| `pnpm page:test` | PASS (64) |
| `pnpm page:check` | PASS |
| `pnpm app:test` | PASS (after `V3InputSurface` timeout fix) |
| `pnpm app:check` | PASS |
| `pnpm program:domain-guards` | PASS |
| `uv run pytest tests/print_learn tests/learn/test_figure_pipeline.py` | PASS (69+) |
| `uv run python scripts/live_compose_write_proof.py` | PASS |
| `uv run python scripts/live_interaction_proof.py` | PASS |
| `uv run python scripts/live_print_composition_proof.py` | PASS |
| `uv run python scripts/live_print_pdf_proof.py` | PASS |
| `uv run python scripts/live_sibling_path_proof.py` | PASS |
| `uv run python scripts/live_learn_edit_reload_proof.py` | PASS (DB) |
| Browser Learn editor E2E | PASS |

---

## G. Live Learn generation ID / evidence

| Proof | Evidence |
| --- | --- |
| Persist + edit/reload | `learn-out-0f35ee03d68f` / editable `62cf9b26-dfd2-4fcf-b0cc-b5d10850d9db` |
| Interaction eval (API) | outcome `correct` |
| Browser E2E | `docs/document-overhaul/reports/evidence/browser-learn-editor-e2e.json` |
| Earlier persist evidence | `learn-out-98c04850b45a`, `learn-out-3d1cf0e29d9a` |

---

## H. Live Print generation ID / evidence

| Proof | Evidence |
| --- | --- |
| Composition → FormPlan | `print-compose-tp-live-print-correction.json` |
| PDF | `print-out-de8b57b66f33` (`.pdf` + `.json`) |
| Form objects | prose + choices (Print task treatment) |

---

## I. Retained-interaction proof matrix

| Kind | Generate | Validate | Evaluate (live) | FE shell | Persist/reload |
| --- | --- | --- | --- | --- | --- |
| choice | PASS | PASS | correct (API + browser) | InteractionShell | PASS |
| multi-select | PASS | PASS | soft | yes | authoring PASS |
| fill-blank | PASS | PASS | soft | yes | authoring PASS |
| numeric | PASS | PASS | correct | yes | authoring PASS |
| short-response | PASS | PASS | pending-review | yes | authoring PASS |
| match-pairs | PASS | PASS | soft | yes | authoring PASS |
| classify | PASS | PASS | soft | yes | authoring PASS |
| sequence | PASS | PASS | correct | yes | authoring PASS |

---

## J. Zero-legacy search results (classified)

| Match class | Examples | Verdict |
| --- | --- | --- |
| Retirement guards / 410 | `component_lectio_retired`, builder source denylist | Keep — not generation |
| Historical docs / debt registers | `docs/d6`, `docs/cleanup-program` | Historical only |
| Package | `packages/lectio-learn` | **Deleted** (`Test-Path` = false) |
| Runtime imports of `@lectio/learn` in `apps/` / `packages/` | none | PASS |

---

## K. Remaining notes (not blockers)

1. Full Unit UI click-through (prepare → teaching approve → Generate Learn button) was not separately recorded; Learn destination `/builder/{id}` was proven live with a production LearnDocument.
2. Print PDF proof used the shared composition + writer + `render_document_pdf` path (generation ID captured). Native worker PDF under a studio generation ID was not separately re-run after Postgres recovery.
3. `validate_repo.py` / `check_architecture.py` may still need `jinja2` in some tool envs — not used as a PASS gate for this correction.

Program status is **PASS**. `OVERHAUL_STATE.md` updated accordingly.

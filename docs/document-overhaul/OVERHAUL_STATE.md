# Document + Interaction Overhaul — State

**Classification**: major  
**Original overhaul branch**: `refactor/document-model-overhaul` (historical)  
**Correction branch**: `fix/document-overhaul-correction`  
**Correction baseline SHA**: `cebb61f2073311b5f7fd2daca8c10ce81e8ed117` (`origin/main`)  
**Started**: 2026-09-10  
**Correction pass**: 2026-09-11

## Current program status

**PASS**

The corrective pass wired real LLM composition/writing, Learn figure asset attachment,
real interaction authoring, one Print composition path, Unit Learn routing,
LearnDocument v2 UI shells, and deleted `packages/lectio-learn`.

Live proofs (production provider + local Postgres + browser):

- Compose + write PASS
- 8/8 interactions PASS
- Print composition PASS
- Print PDF generation ID `print-out-de8b57b66f33`
- Sibling path (same Teaching Plan → Learn + Print independently) PASS
- Learn persist + edit/save/reload API PASS (`learn-out-0f35ee03d68f`)
- Browser Learn editor E2E PASS (`browser-learn-editor-e2e.json`)

See `reports/CORRECTION_REPORT.md` (sections A–K) and `reports/CORRECTION_LEDGER.md`.

Do **not** treat Phase M/N/O historical PASS reports as current evidence.

## Correction waves

- [x] Wave 0 — Baseline + branch
- [x] Wave 1 — Shared `document/` boundary
- [x] Wave 2 — LLM compose + write
- [x] Wave 3 — Learn interactions
- [x] Wave 4 — Print cutover
- [x] Wave 5 — Unit route
- [x] Wave 6 — Learn renderer/editor
- [x] Wave 7 — `@lectio/learn` deletion
- [x] Wave 8 — Verification + report A–K → **PASS**

## Interaction KEEP / DELETE (locked)

**KEEP:** `choice`, `multi-select`, `fill-blank`, `classify`, `match-pairs`, `sequence`, `numeric`, `short-response`  
**DELETE:** `image-hotspot`, `drag-label`, `image-choice`/`image-block`, `video-embed`, spatial actions

## Live proofs recorded (correction)

| Proof | Result |
| --- | --- |
| Live compose + write (`scripts/live_compose_write_proof.py`) | PASS |
| Live 8 interactions (`scripts/live_interaction_proof.py`) | PASS |
| Live Print composition (`scripts/live_print_composition_proof.py`) | PASS |
| Live Print PDF (`scripts/live_print_pdf_proof.py`) | PASS (`print-out-de8b57b66f33`) |
| Live sibling path (`scripts/live_sibling_path_proof.py`) | PASS (`tp-sibling-93b6e7cb`) |
| Live Learn persist + edit/reload | PASS (`learn-out-0f35ee03d68f`, DB) |
| Browser Learn editor E2E | PASS (`browser-learn-editor-e2e.json`) |
| Repo gates (contracts/page/app/domain-guards) | PASS |
| `tests/print_learn` + figure pipeline | PASS |

## Historical notes (not current evidence)

Phases A–O were previously marked complete on `refactor/document-model-overhaul`
with “PASS with deferred debt”. That claim is superseded by this correction pass.

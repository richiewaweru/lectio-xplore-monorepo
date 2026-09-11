# Document Overhaul — Corrective Implementation Ledger

**Branch:** `fix/document-overhaul-correction`  
**Starting SHA (origin/main):** `cebb61f2073311b5f7fd2daca8c10ce81e8ed117`  
**Started:** 2026-09-11  
**Rule:** Do not trust Phase M/N/O PASS reports. Every requirement needs live call-graph proof.

## Progress checklist

- [x] Wave 0 — Baseline + branch
- [x] Wave 1 — Clean shared `document/` boundary
- [x] Wave 2 — Real LLM composition + writing (+ Learn figure pipeline)
- [x] Wave 3 — Real Learn interactions
- [x] Wave 4 — Print cutover (one production path)
- [x] Wave 5 — Unit UI real route
- [x] Wave 6 — Learn renderer/editor
- [x] Wave 7 — Legacy removal / `@lectio/learn`
- [x] Wave 8 — Verification + report A–K

## Program status

**PASS** — see `reports/CORRECTION_REPORT.md`.

## Requirement ledger

| ID | Requirement | Live implementation (at start) | Gap | Code change | Proof |
| --- | --- | --- | --- | --- | --- |
| C1 | LLM document composer | Heuristics only; prompt unused | No LLM compose; 1:1 block→node | `document/composer.py` wired | Live compose PASS |
| C2 | Real document writing | Brief copy stubs | Fake content | `document/writer.py` + `figure_pipeline.py` | Live write PASS |
| C3 | Real Learn interactions | Stub configs on v2 path | Placeholders | Candidate→`interaction_writer` | Live 8/8 PASS |
| C4 | Learn renderer/editor | Mount deferred; asset ID box | No real UI | Shell + editors + figure | Browser E2E PASS |
| C5 | Shared boundary clean | Print/Learn maps in document/ | Leaks | Maps moved to path owners | Domain guards PASS |
| C6 | Print cutover | FormPlan ordinary selection | Dual paths | Composition bridge | Print composition + PDF PASS |
| C7 | Legacy removal | @lectio/learn still large | Deferred debt | Package deleted | Package absent |
| C8 | Unit route | Learn opens Print studio | Unwired | Admit+execute Learn | Wired; builder destination proven |

## Evidence index

| Artifact | Path |
| --- | --- |
| Learn edit/reload | `reports/evidence/learn-out-0f35ee03d68f-edit-reload.json` |
| Browser Learn E2E | `reports/evidence/browser-learn-editor-e2e.json` |
| Print PDF | `reports/evidence/print-out-de8b57b66f33.pdf` |
| Sibling path | `reports/evidence/sibling-tp-sibling-93b6e7cb.json` |

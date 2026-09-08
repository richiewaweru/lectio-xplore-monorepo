# Phase report

Phase: P09 — Run and inspect both product paths live  
Status: **PASS_WITH_BLOCKERS**  
Starting commit: `a88c643` (P08 tip). Ending code: uncommitted product fixes on `feat/unit-print-learn` (see Changes).  
Dirty files preserved: `.tmp/**`, backend log redirects — none committed unless listed.

Contract/spec/prompt versions:

| Artefact | Version / note |
|---|---|
| LIVE_PROTOCOL | pack/verification/LIVE_PROTOCOL.md |
| Live driver | `scripts/run_p09_live_campaign.py` + salvage/export/V05 scripts |
| Alembic | `20260908_0041` (`native_realizations`) applied |
| Learn native policy | catalogue-aligned content/action IDs |

Dependencies verified: P08 PASS (`a88c643`).

## Changes and purpose

### Live product admission repairs

- Chunked approve admits Unit `shared_preparation` + path provenance without print contract v2 at prepare.
- Teaching repairs: brief grounding; assessment sources kind-matched; clear incompatible MC bindings; order-items repair for ordering objectives (empty sources).
- Learn selection/work-orders: `order-items` does not inherit block MC assessment ids.
- Learn policy/selection fallbacks; Sequence preferred when response required.
- Publish admits `source_type=native_learn`.
- PDF: Windows Proactor Playwright thread; contracts `dist/` exports; print API path fix; Poppler page images.
- Campaign: teaching `retry-native` up to 2×; continue Learn if Print fails after teaching approve.

### Live campaign results

| Case | Status | Print gen | Learn | PDF/images | Attempts |
|---|---|---|---|---|---|
| A-cycle | PASS_WITH_BLOCKERS | `b17572f5-…` | produce+publish+instance | PASS (11 pages) | PASS via Sequence salvage |
| B-classification | PASS_WITH_BLOCKERS | `eb867328-…` | produce+publish+instance | PASS (11 pages) | none |
| C-procedure | PASS_WITH_BLOCKERS | `4c4946f5-…` | produce+publish+instance | PASS (6 pages) | none |
| D-visual | PASS_WITH_BLOCKERS | `ff448429-…` | produce+publish+instance | PASS (6 pages) | none |
| V05-failure-recovery | PASS | `3b47668e-…` | Case B sibling release | n/a | n/a — Print fail→retry |

Evidence root: `docs/unit-native-program/evidence/live/`.

Auth: dedicated teacher `p09-live-teacher` via JWT mint (Google Sign-In UI not automated).

## Gate evidence

| Gate ID | Test or command | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|
| P09-V01 | Live case rows A–D | Four filled LIVE_RUN rows | A–D filled with IDs/hashes/providers | PASS_WITH_BLOCKERS | `evidence/live/SUMMARY.json` |
| P09-V02 | Product PDF + page images | Student/teacher PDFs + images | A/B/C/D exported + pdftoppm | PASS | `*/35-*.pdf`, `*/page-images/` |
| P09-V03 | Learn produce/publish/instance | Persisted results | A–D produce/publish/instance; A attempts scored | PASS_WITH_BLOCKERS | `A-cycle/47-attempts.json` |
| P09-V04 | Same teaching hash dual path | Fidelity + timings | Hash per case; dual path from approved teaching | PASS_WITH_BLOCKERS | `*/LIVE_RUN.json` |
| P09-V05 | Controlled recovery + sibling | Sibling intact | Injected `planning_forms` timeout → `retry-native` → ready; Case B `document_hash` unchanged | PASS | `V05-failure-recovery/LIVE_RUN.json` |
| P09-V06 | FINAL_ACCEPTANCE honesty | Enabled/deferred catalogue | Written | PASS | `reports/FINAL_ACCEPTANCE.md` |

## Decisions

D-033 … D-044 (shared prep, assessment kinds, brief grounding, PDF/Windows, order-items salvage, V05 injection).

## Open blockers / next

1. Emit Classify/Numeric learner_actions on B/C teaching so attempts are not Case-A-only.
2. Ground Sequence steps in owned lifecycle vocabulary (not brief-slug fragments).
3. Spatial remains deferred (D-010).
4. Core dual-path acceptance remains **NOT_COMPLETE**; full-catalogue **NOT_COMPLETE**.

## Stop condition

P09 remains PASS_WITH_BLOCKERS. Do not claim core dual-path PASS while B/C lack attempt evidence and Sequence fidelity on A is salvage-quality.

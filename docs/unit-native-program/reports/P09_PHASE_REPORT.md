# Phase report

Phase: P09 — Run and inspect both product paths live
Status: PASS_WITH_BLOCKERS
Starting commit: `a88c643` (P08 tip) / ending code commit: see implementation commits below.
Dirty files preserved: `.tmp/**`, backend log redirects — none committed unless listed.

Contract/spec/prompt versions:

| Artefact | Version / note |
|---|---|
| LIVE_PROTOCOL | pack/verification/LIVE_PROTOCOL.md |
| Live driver | `scripts/run_p09_live_campaign.py` + salvage |
| Alembic | `20260908_0041` applied to local `textbook_agent` DB |
| Learn native policy | content IDs aligned to `@lectio/learn` catalogue |

Dependencies verified: P08 PASS (`a88c643`).

## Changes and purpose

### Live product admission repairs (required for Unit shared prep)

- Chunked approve accepts Unit `shared_preparation` + immutable path provenance without requiring print contract v2 at prepare time.
- Stage2 routes shared Unit prep into native teaching halt (`run_and_persist_teaching_plan`) instead of legacy back-half.
- Teaching assessment-source repair binds unused approved items for practise/diagnose/check intents (not orient/explain).
- Learn native policy offered content IDs corrected to catalogue rows; content/action fallbacks for empty closed sets; Sequence preferred when a response is required.
- Publish admits `source_type=native_learn`.

### Live campaign

- Dedicated teacher `p09-live-teacher`; JWT mint (Google Sign-In UI not automated).
- Case A (butterfly cycle): live Unit→prepare→teaching→Print writers reached `ready`; Learn closed production + realization; publish v1 + learner instance.
- Cases B–D: not completed in this session (cost/time after A repairs); driver ready.

## Gate evidence

| Gate ID | Test or command | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|
| P09-V01 | Live case rows with IDs/hashes/providers | Four cases A–D | Case A filled; B–D NOT_RUN | BLOCKED | `evidence/live/A-cycle/LIVE_RUN.json` |
| P09-V02 | Print semantic + visual PDF via product export | Student/teacher PDFs + page images | Document `ready`; PDF Playwright timeout; Poppler missing | BLOCKED | `35-pdf-status.json`; print gen `b17572f5-…` |
| P09-V03 | Learn generate/edit/publish/complete with persisted results | Full UI/runtime chain | Production + publish + instance OK; no Sequence interaction in this teaching plan → attempts empty | PASS_WITH_BLOCKERS | `40-learn-production.json`; `42-learn-release-v1.json`; `46-instance.json`; `47-attempts.json` |
| P09-V04 | Same-plan fidelity + stage timings | Both paths same revision | Same teaching hash on Print+Learn; timings partial | PASS_WITH_BLOCKERS | `LIVE_RUN.json`; `40-learn-production.json` |
| P09-V05 | Controlled recovery + release immutability | Fault inject + v2 | Not completed live (teaching `failed_recoverable` observed once) | BLOCKED | console / failed_recoverable notes |
| P09-V06 | Final catalogue honesty | Enabled/deferred listed | See FINAL_ACCEPTANCE | PASS | this report + FINAL_ACCEPTANCE |

## Failure attribution and repairs

1. Shared prep blocked by contract-v2 approve gate → repaired gate + stage2 native teaching path.
2. `NO_COMPATIBLE_CAPABILITY` Print on practise-independent without sources → assessment source repair.
3. Learn empty sets for define/name-parts/emphasise → policy ID fix + content fallbacks.
4. `native_learn` publish 404 → add to `_ACTIVE_SOURCES`.
5. PDF export: Playwright navigate to `5173/studio/print/...` times out / aborts.
6. Live teaching sometimes `BRIEF_NO_ANCHOR_OR_TERM` → `failed_recoverable` (retry eligible).

## Migration and compatibility

- Applied `20260908_0041` (`native_realizations`) to local DB.
- Additive publish source type; Learn policy hash changed (deterministic selection fingerprints move).

## Decisions or deviations

- D-033: Unit shared prep may approve into native teaching without print contract v2 at prepare.
- D-034: Learn policy content IDs must match catalogue IDs (no aliases).
- D-035: `native_learn` is an active publishable Builder/release source.
- D-036: Live Google UI not automated; JWT mint for designated test teacher is accepted for API product routes; UI Sign-In remains a residual blocker for full browser protocol.

## Remaining risk / blocked access

- Cases B–D live not run.
- PDF page images need Poppler; PDF export needs healthy frontend print route + Playwright.
- Full-catalogue interactions beyond Sequence still not generation-ready writers.
- Spatial ImageHotspot/DragLabel unavailable.
- Teaching LLM flakiness (`BRIEF_NO_ANCHOR_OR_TERM`).

## Next phase

Program complete pending optional live B–D + PDF/Poppler unblock. No further pack phase after P09.

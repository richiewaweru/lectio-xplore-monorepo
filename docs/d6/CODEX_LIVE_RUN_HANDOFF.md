# Codex Live Run Handoff

## Preconditions
- D6A–D6E PASS (automated Unit-path proof + debt register).
- Branch: `refactor/domain-ownership` @ `c2f8a5cf0202bb1d52658a077a20de68f77e38d7` (plus uncommitted D6 closeout until merged).
- Backend focused suite green (D6A/B/C + Unit-path companions).
- Prefer `render_document_pdf` / non-Playwright PDF path if Playwright hangs (PRINT-001).
- Frontend CI is **not** green (FE-001). Live browser may need local path fixes or known broken imports before a clean UI run — treat FE failures as blockers for UI steps, not as D6 backend regression.

## Do not re-litigate in live run
- LRN-007 over-broad analytics (asserted as-is in D6C).
- DATA-002 recipient/instance linkage shape (current semantics).
- ARCH-005 Print skeleton vs Learn resource-spec roles (backend test uses Learn-compatible admit after Unit prepare).
- LEARN-009 quiz copy / package helpers.
- Product redesign items LRN-001–008, DATA-001–005, PRINT-001.

## Golden browser flow
1. Teacher creates Unit.
2. Generate concepts/path lesson.
3. Generate Print lesson (Unit prepare → approve → generation).
4. Complete required review gates.
5. Export/open PDF (watch for PRINT-001 hang; capture bytes/path if hang).
6. Generate Learn lesson from same Unit path.
7. Open Builder.
8. Edit a meaningful field.
9. Reload and confirm persistence.
10. Preview as Student (confirm no new LearnRelease / unintended instance).
11. Publish LearnRelease (v1).
12. Create class + rolling assignment with ≥2 learners.
13. Open as assigned learner.
14. Complete at least one interaction / attempt.
15. Return as teacher.
16. Verify learner activity in progress/analytics (expect LRN-007 breadth if self-started instances exist).

## Optional second publish
- Edit draft → publish v2 → confirm v1 immutable (mirrors D6B).

## Capture
- Screenshots per step
- Timestamps
- Browser console errors
- Backend errors / stack traces
- IDs: Unit, PathLesson, generation(s), Learn document, LearnRelease (v1/v2 hashes), class, assignment, recipient, learning_instance, attempt
- PDF file or failure mode (PRINT-001)
- Final verdict: PASS / PARTIAL / FAIL with debt IDs for any product gaps

## Automated proof already done (Cursor D6)
| Segment | Evidence |
|---|---|
| Unit→Print + retry + PDF | `tests/planning/test_d6a_unit_print_integration.py` |
| Unit→Learn→Builder→Publish v1/v2 | `tests/routes/test_d6b_unit_learn_publish.py` |
| Assignment→runtime→analytics | `tests/routes/test_d6c_learn_runtime_chain.py` |
| Guards / Alembic / page | `docs/d6/reports/D6D/PHASE_REPORT.md` |
| Debt register | `docs/architecture/TECHNICAL_DEBT.md` |

## Out of scope for this handoff document
- Do not execute the browser flow in the D6 Cursor phase.
- Do not restore retired legacy trees or redesign evaluation/auth.

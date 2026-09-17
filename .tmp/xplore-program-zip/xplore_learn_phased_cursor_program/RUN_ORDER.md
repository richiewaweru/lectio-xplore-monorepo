# Run Order

Run these sequentially. One phase per Cursor implementation run.

1. `phases/00-baseline/CURSOR_PHASE_PROMPT.md`
2. `phases/01-consolidation/CURSOR_PHASE_PROMPT.md`
3. `phases/02-learn-cleanup/CURSOR_PHASE_PROMPT.md`
4. `phases/03-learn-document-ui/CURSOR_PHASE_PROMPT.md`
5. `phases/04-interactions/CURSOR_PHASE_PROMPT.md`
6. `phases/05-publishing/CURSOR_PHASE_PROMPT.md`
7. `phases/06-runtime/CURSOR_PHASE_PROMPT.md`
8. `phases/07-evidence/CURSOR_PHASE_PROMPT.md`
9. `phases/08-classes/CURSOR_PHASE_PROMPT.md`
10. `phases/09-assignments/CURSOR_PHASE_PROMPT.md`
11. `phases/10-student-product/CURSOR_PHASE_PROMPT.md`
12. `phases/11-teacher-insight/CURSOR_PHASE_PROMPT.md`
13. `phases/12-hardening/CURSOR_PHASE_PROMPT.md`

## Important

Do not instruct Cursor to automatically continue into the next phase after finishing one. Start a fresh run for each phase so:
- context stays manageable,
- the phase report is written before the next phase,
- the next agent run must recover actual state,
- failures are localized,
- drift is easier to diagnose later.

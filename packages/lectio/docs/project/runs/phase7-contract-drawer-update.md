## Feature: Persistent Contract Drawer Update

**Classification**: minor
**Subsystems**: frontend

### Progress
- [x] Understood requirements and identified scope
- [x] Read relevant source code and project rules
- [x] Implemented the change
- [x] Wrote tests for new behavior
- [x] Ran validation (backend: ruff + pytest, frontend: check + build)
- [x] Self-reviewed against agents/standards/review.md
- [ ] Wrote commit message(s) following agents/standards/communication.md
- [ ] Updated PR description with summary, validation evidence, risks
- [x] Noted any follow-up work or open questions

### Validation Evidence
- `npm run check`
- `npm run test`
- `npm run build`

### Risks and Follow-up
- The template detail page now uses a persistent left-side contract drawer on `md+` and a temporary left-side sheet on mobile, with desktop state remembered via `localStorage`.
- Svelte build still reports the pre-existing large-chunk warning for the client bundle. No new build errors or warnings were introduced by this update.
- Commit/PR steps are still pending because this pass stopped at local implementation and validation.

## Feature: library reference docs

**Classification**: minor
**Subsystems**: frontend, docs

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
- `C:\Projects\lectio`: `npm run check` -> passed with 0 errors and 0 warnings
- `C:\Projects\lectio`: `npm run build` -> passed
- `C:\Projects\lectio_nextjs`: `npm run validate` -> passed
- Docs reviewed in:
  - `C:\Projects\lectio\docs\reference\component-guide.md`
  - `C:\Projects\lectio_nextjs\docs\reference\component-guide.md`

### Risks and Follow-up
- This was a docs-only change, so no new behavior-specific test cases were required.
- No commit or PR description was created in this turn because the user asked for authored docs, not a git handoff.

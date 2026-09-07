## Feature: Sidebar Navigation Alignment

**Classification**: minor
**Subsystems**: frontend, docs

### Progress
- [x] Understood requirements and identified scope
- [x] Read relevant source code and project rules
- [x] Implemented the sidebar navigation helper and shared shell wiring
- [x] Wrote tests for new behavior
- [x] Ran validation (backend: ruff + pytest, frontend: check + build)
- [x] Self-reviewed against agents/standards/review.md
- [x] Wrote commit message(s) following agents/standards/communication.md
- [x] Updated handoff/runbook summary, validation evidence, risks
- [x] Pushed the sidebar navigation change to GitHub
- [x] Noted any follow-up work or open questions

### Validation Evidence
- `npm run check`
- `npm run test`
- `npm run build`

### Risks and Follow-up
- The desktop sidebar now reads from a shared navigation helper so stable components such as `ComparisonGrid` and `TimelineBlock` stay in sync with the live registries.
- The Svelte build still reports the pre-existing large-chunk warning for the client bundle.
- Initial feature push for this phase landed on `master` as `66038a7`.

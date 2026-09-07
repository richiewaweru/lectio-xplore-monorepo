## Feature: library runtime surfaces and template expansion

**Classification**: major
**Subsystems**: frontend, contracts, docs

### Progress
- [x] Understood requirements and identified scope
- [x] Read relevant source code and project rules
- [x] Audited the ahead commit and uncommitted workspace changes
- [x] Cleaned root-level scratch artifacts into proper project docs
- [x] Updated developer-facing docs for packaging, runtime surfaces, and contract exports
- [x] Added missing template READMEs for the new registry entries
- [x] Ran validation (`check`, `test`, `build`, `package`, `export-contracts`)
- [x] Self-reviewed against agents/standards/review.md
- [x] Wrote commit message(s) following agents/standards/communication.md
- [x] Pushed the current source of truth to GitHub
- [x] Noted follow-up work or open questions

### Validation Evidence
- `npm run check`
  - Passed on March 19, 2026 with 0 errors and 0 warnings.
- `npm run test`
  - Passed on March 19, 2026.
  - Result: 4 test files passed, 36 tests passed.
  - Note: the expected `GlossaryRail` soft-capacity warning still appears in test stderr because the physics fixture intentionally exceeds the warning threshold.
- `npm run build`
  - Passed on March 19, 2026.
  - The client build still reports one chunk over 500 kB after minification, but the production build completed successfully.
- `npm run package`
  - Passed on March 19, 2026.
  - `src/lib` packaged to `dist`.
- `npm run export-contracts`
  - Passed on March 19, 2026.
  - Exported 12 template contracts, 1 component field map, 1 component registry, and 1 preset registry.

### Risks and Follow-up
- The app build still emits a large client-chunk warning; the library is functional, but later chunk-splitting or route-splitting may be worthwhile.
- The repo still carries older internal template harness files for showcase and regression coverage. Consumers should treat the registry plus the public runtime surfaces as the source of truth.
- Whenever templates, presets, component metadata, or library exports change again, rerun both `npm run package` and `npm run export-contracts`, then commit the refreshed `agents/contracts/` snapshots.

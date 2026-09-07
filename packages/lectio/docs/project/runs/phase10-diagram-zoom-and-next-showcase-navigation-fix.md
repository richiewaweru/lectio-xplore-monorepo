## Bugfix: Diagram inspect centering

**Classification**: minor
**Root cause**: `DiagramBlock` relied on default dialog placement instead of an explicit centered portal layout, so the enlarged inspect surface could open too close to the viewport edge.

### Progress
- [x] Reproduced the bug (or identified the failing code path)
- [x] Identified root cause
- [x] Implemented the fix
- [x] Added regression test
- [x] Ran validation
- [x] Self-reviewed the diff

### Validation Evidence
- `npm run check`
- `npm run test`
- `npm run build`

### Risks
- The fix is intentionally scoped to `DiagramBlock`; other dialog-based components were not repositioned in this pass.
- Manual browser smoke was not run from the desktop after the code change, so the automated regression suite is the primary verification here.
- `npm run build` still emits the existing large-chunk warning.

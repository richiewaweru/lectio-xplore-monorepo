# Cursor Master Prompt

Target workspace: `C:\Projects\lectio`

Execute this as a strict canonicalization + cleanup refactor.

Before every phase read:
1. every file under `permanent/`,
2. current phase `CURSOR_PROMPT.md`,
3. `docs/cleanup-program/CLEANUP_STATE.md` if present,
4. `docs/cleanup-program/REACHABILITY_MANIFEST.json` if present,
5. previous phase report.

Rules:
- Unit path is canonical.
- Inspect before moving or deleting.
- Deletion requires evidence.
- Do not preserve legacy code merely because legacy tests reference it.
- Preserve migration history.
- Split mixed modules where necessary.
- Intentional surface-specific duplication is allowed when it improves separation.
- Do not implement deferred product fixes.
- Stop on BLOCKED or FAIL.
- One phase at a time.

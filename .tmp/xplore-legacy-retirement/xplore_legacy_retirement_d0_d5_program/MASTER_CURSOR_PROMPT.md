# Master Cursor Prompt

Workspace: C:\Projects\lectio

Before every phase read:
- all permanent/*
- current phase CURSOR_PROMPT.md
- docs/legacy-retirement/LEGACY_STATE.md
- docs/legacy-retirement/LEGACY_DEPENDENCY_MANIFEST.json
- previous phase report

Rules:
- Unit path is canonical.
- inspect before deleting.
- migrate live consumers first.
- compatibility shims are temporary.
- preserve migration history.
- remove legacy-only tests/docs/config with the retired feature.
- no deferred product fixes.
- one phase at a time.

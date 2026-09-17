# Reuse Before Replace Policy

Every phase must classify touched subsystems as:

- **REUSE AS-IS**
- **EXTEND**
- **REFACTOR**
- **REMOVE**
- **NEW**

New files are not forbidden. New parallel *subsystems* are.

## Known existing seams that should be treated as preferred reuse candidates

Current component-Xplore has already demonstrated:
- generation → Builder hydration
- editable `LessonDocument`
- block/field mutations
- section ordering
- undo/redo/history
- block duplication/removal
- local IndexedDB persistence
- server persistence
- sync queue/offline fallback
- lesson CRUD
- component renderer/registry
- generation polling/stream insertion
- concept/path/unit DB models
- editable lesson persistence

Phase 0 must verify the actual state rather than assume these exact file paths survived consolidation.

## New-subsystem justification

Any phase adding a significant new subsystem must include in its report:

1. Existing seam inspected.
2. Why bounded extension was insufficient.
3. Why the new ownership boundary is semantically correct.
4. How duplicate state/source-of-truth is avoided.
5. Tests proving no regression to reused behavior.

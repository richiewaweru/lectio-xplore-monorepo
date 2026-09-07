# D6_STATE

- current_subphase: DONE
- last_completed_subphase: D6E
- branch: refactor/domain-ownership
- sha: c2f8a5cf0202bb1d52658a077a20de68f77e38d7
- dirty_state: D6 docs + D6A–C tests + wiring fixes + Alembic 20260907_0040 uncommitted

## Gates
- [x] D6A
- [x] D6B
- [x] D6C
- [x] D6D
- [x] D6E

## Known failing canonical tests
- `@lectio/learn` quiz evaluate ("Not quite!") — LEARN-009
- Frontend vitest/svelte-check/build import path drift — FE-001

## Environment limitations
- Playwright PDF export avoided (PRINT-001); D6A uses `render_document_pdf`.

## New debt discovered
- ARCH-004: fixed (Unit prepare context clobber in `dispatch.py`)
- ARCH-005: Print skeleton slots vs Learn resource-spec roles (D6B)
- LRN-010: fixed (`_utcnow` shim import in `runtime_routes.py`)
- DATA-006: fixed (missing Alembic `20260907_0040` migration file)
- FE-001: frontend alias/path drift after Print/Learn ownership moves

## Ready for Codex live run
YES

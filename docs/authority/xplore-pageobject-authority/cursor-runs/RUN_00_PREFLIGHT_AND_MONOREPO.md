# Cursor Run 00 — Preflight and Monorepo Import

## Goal

Create `C:\Projects\lectio` safely, import both source histories, establish baseline commands, and map the exact current code owners before any product edits.

## Mandatory authority

Read the root authority pack first. This run may not change application behavior.

## Procedure

1. Inspect `C:\Projects\lectio - Copy`:
   - verify it is the Lectio page-object repository;
   - record branch, HEAD, remotes, and `git status --porcelain`;
   - confirm catalogue version 1.1.0 and contract files.
2. Confirm `C:\Projects\lectio` is absent or empty.
3. Run the provided bootstrap script in history-preserving mode.
4. Confirm imported paths:
   - `packages/lectio-page`
   - `apps/textbook-agent`
5. Confirm `apps/textbook-agent` imported the remote `xplore` branch, not default main/v3.
6. Discover existing toolchain commands from package/README/pyproject files. Do not invent replacements.
7. Run baseline tests/check/build categories and record existing failures.
8. Build `docs/implementation-runs/BASELINE_MAP.md` resolving every item listed in `BASELINE.md`.
9. Search and record all references to:
   - `ComponentSlot`
   - `run_component_selector`
   - `SectionContent`
   - `_component_order`
   - `BLOCK_FIELD_ORDER`
   - visual attachment/writeback symbols
   - question assembly and practice bucket logic
   - document render and PDF routes
10. Create root `PROGRESS.md` and `BLOCKERS.md`.

## Stop conditions

- local Lectio source is dirty;
- target root is non-empty;
- xplore cannot be fetched;
- baseline test commands cannot be identified;
- source import would destroy either original repository.

## Gate

No product files changed. Both projects run from the new root. Exact current owners are documented with paths and symbols.

## Commit

`chore(monorepo): import xplore and lectio page package`

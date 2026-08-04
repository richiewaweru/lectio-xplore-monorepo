# Agents — @lectio/page

## Entry

Read `agents/ENTRY.md`, then `agents/project.md`.

## Project rules

- This package is **page-object / document-first**, not a component library.
- Do not reintroduce `SectionContent`, `component_id`, `section_field`, `printMode`, or `@media print` stripping.
- Only `aside` may use a border or background.
- Contracts live in `contracts/` and are exported via `pnpm export-contracts`.
- Architecture briefs live in `docs/architecture/page-objects/`.
- Legacy Lectio stays in `C:\Projects\lectio` — do not couple to it.

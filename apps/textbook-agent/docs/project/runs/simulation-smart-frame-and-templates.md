## Feature: Simulation Smart Frame & Two Simulation-First Templates

**Classification**: medium
**Subsystems**: lectio (components, templates, types, registry), backend (pipeline types), cross-repo type sync
**Scope**: SimulationBlock component rewrite, two new templates with live simulations, type system extension

### Progress
- [x] Extended `SimulationContent` type with `html_content` field (TypeScript + Python mirror)
- [x] Rewrote `SimulationBlock.svelte` as a smart iframe frame with chrome controls
- [x] Designed and implemented `interactive-lab` template (config, layout, presets, preview)
- [x] Designed and implemented `guided-discovery` template (config, layout, presets, preview)
- [x] Hand-crafted F=ma graph slider simulation HTML for interactive-lab preview
- [x] Hand-crafted probability tree simulation HTML for guided-discovery preview
- [x] Added simple live simulation to component gallery dummy content
- [x] Registered both templates in `template-registry.ts`
- [x] Added both templates to `scripts/export-contracts.ts`
- [x] Exported contracts to `backend/contracts/` (12 total)
- [x] Ran `svelte-check` — 0 errors, 0 warnings, 4569 files
- [x] Ran `npm run package` — built clean
- [ ] Visual browser smoke test of simulation rendering and expand/collapse
- [ ] Run full Textbook Agent frontend validation (`npm test`, `npm run check`, `npm run build`)

### Validation Evidence

| Command | Result |
| --- | --- |
| `npx svelte-check --tsconfig ./tsconfig.json` in `lectio/` | 0 errors, 0 warnings, 4569 files |
| `npm run package` in `lectio/` | Built to `dist/` (tooltip `.d.ts` warning is pre-existing from bits-ui) |
| `npx tsx scripts/export-contracts.ts` in `lectio/` | 12 template contracts, 23 components, 5 presets exported |

### Risks and Follow-up
- The three hand-crafted simulations are developer-authored test fixtures. In production, the pipeline's interaction node will generate these HTML documents per section.
- The `sandbox="allow-scripts"` policy on the iframe is intentionally restrictive (no forms, no navigation, no top-level access). If future simulation types need `allow-forms` or `allow-same-origin`, the sandbox policy must be reviewed case by case.
- The Textbook Agent frontend has not been re-validated after this Lectio change. Run `npm test`, `npm run check`, and `npm run build` in `frontend/` to confirm compatibility.
- The `tooltip` `.d.ts` generation warnings from `npm run package` are pre-existing and unrelated.

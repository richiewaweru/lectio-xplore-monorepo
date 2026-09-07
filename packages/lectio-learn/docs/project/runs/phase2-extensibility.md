## Handoff — Phase 2: Component Extensibility

**Commit**: `bb975f4`

**What changed**:
- Extended all 8 components with optional customizability fields for real educational use cases
- `HookHeroContent`: added `image?` with onerror fallback
- `ExplanationContent`: added `callouts?` (remember/insight/sidenote) with lucide icons
- `DefinitionContent`: added `examples?`, `related_terms?` (Badge display)
- `WorkedExampleContent`: added `answer?`, `alternatives?` (Collapsible)
- `PracticeProblem`: added `hints?` (tiered array), `answer?`, `solution?` — backward compat with single `hint`
- `PitfallContent`: added `examples?` (array), `why?` — backward compat with single `example`
- `GlossaryTerm`: added `related?` cross-references
- `WhatNextContent`: added `prerequisites?`
- Updated `registry.ts` capacity entries and `validate.ts` with new field warnings
- Expanded `dummy-content.ts` to showcase all new fields

**Current state**: Every component accepts its extended optional fields. A PracticeStack with one hint looks simple; with three tiered hints and a worked solution, it's the same component with more props.

**Validated**:
- `npm run check` — 0 errors (5 benign `state_referenced_locally` warnings)
- All new fields render correctly in component showcase
- Backward compatibility preserved: old content shape still works

**Not done yet**: Visual styling still uses cold defaults (system fonts, flat shadows, small radius). GlossaryRail doesn't scroll.

**Start here**: `src/lib/types.ts` for the full field list, `src/lib/dummy-content.ts` to see all fields in use

**Risks**: `PracticeProblem` has both `hint` (string) and `hints` (string[]) — the component's `getHints()` normalizes them, but this dual pattern adds complexity. Phase 4 later cleaned this up with structured `PracticeHint[]`.

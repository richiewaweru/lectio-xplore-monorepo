## Handoff — Phase 4: Complete Component Build

**Commit**: `a340a43`

**What changed**:

### Infrastructure (full rewrites)
- `src/lib/types.ts` — 21 component interfaces, shared primitives (Difficulty, GradeBand, HintLevel, BehaviourMode), structured PracticeHint/PracticeSolution, SectionHeaderContent, full SectionContent with all optional fields
- `src/lib/registry.ts` — 21 entries with `status`, `group` fields, helper functions (`getStableComponents`, `getComponentsByGroup`)
- `src/lib/validate.ts` — validators for all content types, handles `worked_example`/`worked_examples[]`, `pitfall`/`pitfalls[]`
- `src/lib/dummy-content.ts` — restructured `calculusSection` (header sub-object, PracticeHint format), added `physicsSection` (Newton's Second Law) with inline SVG diagrams

### New UI primitives (wrapping bits-ui v2)
- `src/lib/components/ui/popover/` — Popover, PopoverTrigger, PopoverContent
- `src/lib/components/ui/dialog/` — Dialog, DialogTrigger, DialogContent, DialogOverlay, DialogClose, DialogTitle, DialogDescription
- `src/lib/components/ui/tooltip/` — Tooltip, TooltipTrigger, TooltipContent, TooltipProvider

### 12 new educational components
- **Group 1**: SectionHeader (title/subtitle/objective/level pills), PrerequisiteStrip (Popover refreshers), InterviewAnchor (speech prompt with audience)
- **Group 2**: DefinitionFamily (composes DefinitionCard), GlossaryInline (inline Popover on dotted-underline terms), InsightStrip (2-3 cell CSS grid)
- **Group 3**: ProcessSteps (numbered steps with connectors, input/output, warnings, checklist mode)
- **Group 4**: QuizCheck (option buttons with correct/incorrect feedback, try-again), ReflectionPrompt (type variants: open, sentence-stem, timed, pair-share)
- **Group 6**: DiagramBlock (SVG + callout overlays + zoom Dialog), DiagramCompare (before/after with CSS clip-path slider), DiagramSeries (step nav through SVG sequence)

### Updated existing components
- PracticeStack: migrated from `string[]` hints to `PracticeHint[]` with levels, `PracticeSolution` with approach/answer/worked
- PitfallAlert: added `severity?` support (major=orange, minor=amber styling)

### New template + routes
- `src/lib/templates/EnrichedLearningPath.svelte` — full template using all 20 components
- `src/routes/templates/+page.svelte` — template switcher (GuidedConceptPath vs EnrichedLearningPath)
- `src/routes/components/+page.svelte` — all 20 components with live previews
- `src/routes/+layout.svelte` — added EnrichedLearningPath to sidebar

**Current state**: 20 renderable components (SimulationBlock is type-only, status: beta). Two templates: GuidedConceptPath (calculus, original 8 components) and EnrichedLearningPath (physics, all 20). Full type system, registry, and validation. Component showcase shows every component with live previews.

**Validated**:
- `npm run check` — 0 errors
- TypeScript compiles clean (`npx tsc --noEmit`)
- All pushed to `origin/master`

**Not done yet**:
1. SimulationBlock — registered as type-only, needs interaction pipeline to build
2. KaTeX rendering — `notation?` and `formula?` fields exist in types but components don't yet call `katex.renderToString()` (katex is installed)
3. GlossaryInline is a standalone component but not wired into ExplanationBlock prose (would need `{@html}` integration)
4. DiagramBlock callout positioning may need tuning with real SVG content
5. Print styles (`.print-only`) are defined but not fully tested in print media
6. No tests — consider adding component tests with vitest + @testing-library/svelte

**Start here**:
- New components: `src/lib/components/lectio/` (12 new .svelte files)
- Types: `src/lib/types.ts` (complete schema)
- Physics content: `src/lib/dummy-content.ts` (`physicsSection`)
- New template: `src/lib/templates/EnrichedLearningPath.svelte`

**Risks**:
- `SectionContent` breaking change: `header: SectionHeaderContent` replaced top-level `title`/`subject`/`grade_band`. Any external consumers of the old shape will break.
- `PracticeProblem` breaking change: `hints` is now `PracticeHint[]` (objects with level+text), not `string[]`. Old flat hint format no longer works.
- DiagramBlock uses `{@html content.svg_content}` — safe for author-controlled content but would be an XSS vector if user-supplied SVG is ever passed in.
- Popover/Dialog/Tooltip are minimal bits-ui re-exports without styled wrapper components. If positioning or theming issues arise, may need styled wrappers like shadcn-svelte provides.

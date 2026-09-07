## Handoff — Phase 3: Visual Polish

**Commit**: `ba96a95`

**What changed**:
- Loaded Google Fonts (Fraunces serif + Public Sans) in `app.html`
- Rewrote `app.css` with warm HSL palette: beige background `hsl(38,52%,96%)`, navy foreground `hsl(213,37%,17%)`, orange accent `hsl(24,95%,53%)`
- Increased border radius to 1rem, added warm shadows (`--shadow-warm`, `--shadow-warm-sm`)
- Added styled scrollbar CSS (`.scrollbar-styled`), emphasis highlights (`.lectio-emphasis`), step-reveal animation
- Base UI updates: Card (`rounded-2xl`, `shadow-warm-sm`), Button (`rounded-xl`, `transition-all`), Alert (`rounded-2xl`), ScrollArea (`scrollbar-styled`)
- All 8 educational components updated with warmer colors, serif headings, rounded corners
- GlossaryRail: dark navy theme (`bg-primary text-primary-foreground`), frosted glass term cards, fixed scroll heights
- Layout + pages: `font-serif` on all headings and brand text, `rounded-xl` on home buttons
- Fixed sticky GlossaryRail by removing `overflow-y-auto` from `<main>`
- Expanded glossary dummy content to 10 terms to demonstrate scrolling

**Current state**: Warm beige palette, Fraunces serif headings, smooth transitions throughout. GlossaryRail is dark navy with scrollable frosted-glass term cards. Matches the Next.js reference visual quality.

**Validated**:
- `npm run check` — 0 errors
- Visual inspection: all pages render with warm palette, serif fonts, smooth interactions
- GlossaryRail scrolls and sticks correctly
- All interactive behaviors preserved (no logic changed)

**Not done yet**: Only 8 of 21 components exist. The build doc specifies 13 more.

**Start here**: `src/app.css` for the design system, any `src/lib/components/lectio/*.svelte` for component styling patterns

**Risks**: `.lectio-emphasis` is a CSS class (not Tailwind utility) because Tailwind can't scan `{@html}` strings. If changing the emphasis styling, edit `app.css` directly.

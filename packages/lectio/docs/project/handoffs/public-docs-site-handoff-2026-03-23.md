# Public Documentation Site Handoff (`/docs`)

## Scope

In-app documentation for the Lectio showcase (same SvelteKit app as components and templates), with global navigation, mobile doc jump control, and content consolidated from README, `docs/reference/*`, and the Textbook Agent integration pattern.

## What Changed

### Routes and content

- Added `src/routes/docs/+layout.svelte` with `DocsMobileNav` and `doc-prose` shell.
- Added `src/routes/docs/+page.svelte` as documentation home (grouped links mirroring IA).
- Added doc pages:
  - `introduction` — what Lectio is, audience, relation to showcase.
  - `installation` — `npm run package`, `file:` dependency, peer deps, `lectio/theme.css`.
  - `concepts` — `SectionContent`, registry, templates, presets, validation.
  - `rendering` — `TemplatePreviewSurface` / `TemplateRuntimeSurface` vs `LectioThemeSurface` + `template.render` (code sample built in TS to avoid nested `<script>` parsing issues).
  - `contracts` — `export-contracts`, JSON artifacts, pipeline rule (no `src/` imports from agents).
  - `best-practices` — pedagogical use, capacities, KaTeX, contracts freshness.
  - `examples/textbook-agent` — multi-section pattern aligned with Textbook Agent `LectioDocumentView`.
  - `reference` — pointers to repo markdown (`docs/reference/*`, `docs/components/*`, `README.md`, TS sources of truth).

### Navigation

- Added `src/lib/navigation/docs-navigation.ts` — grouped nav config (`getDocsNavigation`, `flattenDocsNavItems`).
- Added `src/lib/navigation/DocsMobileNav.svelte` — `<select>` jump nav for viewports below `xl` (uses `$app/state` + `goto`).
- Extended `src/lib/navigation/AppSidebar.svelte` with a **Documentation** section above Components/Templates.

### Showcase shell

- Updated `src/routes/+page.svelte` — primary CTA **Read the docs** → `/docs`; components and templates as secondary actions.

### Styling

- Extended `src/app.css` with `@layer components` rules for `.doc-prose` (headings, lists, links, pre/code, tables) and `.doc-callout`.

### Intentionally excluded

- No links to `docs/project/` handoffs or internal runbooks in the public nav.
- No mdsvex dependency; pages are Svelte for predictable compilation (especially fenced examples).

## Validation

- `npx svelte-check --tsconfig ./tsconfig.json` — 0 errors.
- `npm run build` — passed.
- `npm run test` — 36 tests passed.

## Known Follow-Up

- If the site is deployed under a subpath, set `paths.base` in `svelte.config.js` and prefer `$app/paths` for internal links (anchors today use root paths).
- Longer term, consider mdsvex or a content folder if prose volume grows and duplication with `docs/reference/*.md` becomes painful.
- Sidebar remains hidden below `xl`; docs rely on `DocsMobileNav` on small screens — spot-check UX on real devices after deploy.

## Where To Start Next Time

- Nav IA and labels: `src/lib/navigation/docs-navigation.ts`.
- New doc page: add route under `src/routes/docs/…/+page.svelte` and register the item in `docs-navigation.ts`.
- Prose styling: `src/app.css` (`.doc-prose`, `.doc-callout`).
- Example that includes Svelte `<script>` in a code block: define the string in `<script lang="ts">` and split `'</' + 'script>'` so the module parser does not close early.

# Track A — Learn renderer (G1)

- [x] Read doc36, Track A brief, repository standards, and inspect the existing Learn path.
- [x] Implement A1–A7 within the frontend Learn renderer and student shell ownership.
- [x] Add focused renderer regression coverage.
- [x] Run `pnpm test -- --maxWorkers=2`, `pnpm run check`, and production build.
- [x] Capture 1280px and 390px golden/legacy/overlong screenshots and keyboard/DOM evidence.
- [x] Record visual differences and unticked items.

## Evidence

Evidence is under `docs/doc36-presentation/evidence/track-a/`:

- `g1-app-test.log`: 67 files, 284 tests passed.
- `g1-app-check.log`: 0 errors, 5 pre-existing warnings.
- `g1-build.log`: production build passed.
- `g1-browser-dom.json`: golden/legacy/overlong at 1280 and 390; all have `scrollWidth === innerWidth`, no learner ID/count attributes, and no V2/nodes text.
- `g1-keyboard-dom.txt`: keyboard selection changed the prediction option to selected and enabled its action button.
- `golden-{desktop,mobile}.png`, `legacy-{desktop,mobile}.png`, `overlong-{desktop,mobile}.png`: fixture captures.
- `reference/*.png`: five supplied artboard captures, with UUID provenance in `reference/README.md`.

Known reference differences: the supplied figure artwork labels/legend are not present in the reused SVG asset, the application keeps its existing Fraunces display serif, and the learner shell has subject-only metadata when no lesson-number context is provided. These are recorded for the parent visual review; authored lesson wording remains fixture-driven.

Unticked: production learner screenshots require an authenticated lesson route; the dev fixture route is intentionally development-only and its server/endpoint guard remains in Phase 0.

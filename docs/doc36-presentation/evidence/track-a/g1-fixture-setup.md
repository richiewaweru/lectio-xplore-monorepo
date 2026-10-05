# Reproducible fixture capture

Captured at `2026-10-05T14:56:46.436Z` from commit `c34645b2` plus the final G1 correction working tree.

1. Start the frontend with `pnpm dev -- --host 127.0.0.1 --port 5181` from `apps/textbook-agent/frontend`.
2. The dev-only `/dev/shared-lesson/[fixture]` exemption in `src/lib/shared/auth/routing.ts` is enabled only when `$app/environment` reports `dev`; it is covered by `routing.test.ts`.
3. The fixture page accepts only `golden`, `legacy`, and `overlong`; its JSON and SVG endpoints remain guarded and return 404 in production.
4. Capture each fixture at 1280×900 and 390×844 after the page settles, saving the full-page PNGs beside this file.

The production route retains the normal authentication redirect. No token, user data, or production auth behavior was changed.

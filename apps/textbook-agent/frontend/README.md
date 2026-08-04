# Frontend

SvelteKit client for the Textbook Generation Agent.

## Commands

```bash
npm ci
npm run dev
npm run check
npm run build
npm run test
```

## Notes

- Native frontend config lives in `frontend/.env`.
- `PUBLIC_API_URL` is the canonical browser API base.
- Google sign-in accepts `PUBLIC_GOOGLE_CLIENT_ID` or `VITE_GOOGLE_CLIENT_ID` in native frontend runs. `PUBLIC_GOOGLE_CLIENT_ID` is preferred for Vercel/static builds.
- `VITE_API_TARGET` is optional and only used as a dev-proxy override.
- API calls use `PUBLIC_API_URL` when set, otherwise they fall back to same-origin paths.
- Generation pages hydrate from the saved JSON document endpoint and continue with authenticated SSE updates.
- Textbooks render natively with Lectio components; the legacy HTML `iframe` viewer is no longer part of the live app.
- The frontend imports `lectio/theme.css` so previews and generated documents use Lectio's shared runtime visuals.
- Only the fully wired `blue-classroom` preset is exposed in-product right now; other preset ids remain supported in data but are not yet live UI choices.
- Docker builds serve the compiled static app from `nginx:alpine`; the repo-root `GOOGLE_CLIENT_ID` is mapped into the Docker build as `VITE_GOOGLE_CLIENT_ID`.
- Vercel should deploy from `frontend/` with `npm install`, `npm run build`, output directory `build`, and env vars `PUBLIC_API_URL` plus `PUBLIC_GOOGLE_CLIENT_ID` or `VITE_GOOGLE_CLIENT_ID`.
- Lectio is consumed from the published npm package pinned in `package.json`; no vendored Lectio copy is used in this repo.

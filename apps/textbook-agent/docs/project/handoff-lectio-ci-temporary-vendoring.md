# Handoff: Temporary Lectio + Contracts CI Self-Containment Fix

**PR**: [#15](https://github.com/richiewaweru/text-book-generator/pull/15)  
**Related commits**: `f549ca6`, `dd0f17a`  
**Merged via**: `52ca915`  
**Date**: `2026-03-31`  
**Status**: merged to `main` as a temporary fix

---

## Why This Handoff Exists

This handoff covers the CI-specific follow-up that was required after the main platform restructure had already passed local validation.

The important distinction is:

- Lectio usage in the frontend was **not** new
- the new part was making CI able to resolve the dependency and its contract inputs without access to the developer's local sibling repo

---

## Original Problem

### 1. Frontend dependency was machine-local

Before the fix, `frontend/package.json` contained:

- `lectio: "file:../../lectio"`

That worked locally because the developer machine had:

- `C:\Projects\lectio`

GitHub Actions does **not** check out that sibling repo, so CI could not resolve the `lectio` package at all.

### 2. Backend contract exports existed locally but were ignored

Local backend validation was also benefiting from the presence of exported contract JSON files under:

- `backend/contracts/`

Those files existed on disk locally, but the repo `.gitignore` treated them as generated outputs and did not commit them. In CI, the folder was therefore missing and contract-loading tests failed.

---

## How The Failure Showed Up

### Backend CI failure

`backend-quality` failed because tests that depend on `backend/contracts/*.json` could not find:

- `component-registry.json`
- `component-field-map.json`
- template contract JSONs
- preset registry JSONs

The contract loader raised `FileNotFoundError` in CI.

### Frontend CI failure

`frontend-quality` failed because Vite and `svelte-check` could not resolve the `lectio` package.

Symptoms included:

- `Cannot find module 'lectio' or its corresponding type declarations`
- build resolution failures for package entry resolution

---

## What Was Changed

## 1. Backend contract catalog was committed

The `.gitignore` rules were changed so `backend/contracts/*.json` could be committed while still allowing normal output ignores elsewhere.

Committed files now include:

- `backend/contracts/component-registry.json`
- `backend/contracts/component-field-map.json`
- `backend/contracts/preset-registry.json`
- the live template contract JSON files

This made backend tests and contract loading deterministic in CI.

## 2. Frontend stopped pointing at `../../lectio`

`frontend/package.json` was changed from:

- `file:../../lectio`

to:

- `file:./vendor/lectio`

That means the frontend package now resolves `lectio` from inside this repo rather than from a sibling checkout.

## 3. A vendored package shell was added

Added:

- `frontend/vendor/lectio/package.json`

This package manifest exposes the `dist` entrypoints and allows npm/Vite/SvelteKit to resolve the dependency like a normal package.

## 4. The built Lectio runtime artifacts were committed

Added:

- `frontend/vendor/lectio/dist/`

This contains the built JS, DTS, Svelte component files, template runtime files, and CSS needed by the frontend package consumer.

Important note:

- this `dist` was copied from the sibling `C:\Projects\lectio\dist`
- it was **not** rebuilt from source inside this repo during the merge process

## 5. Ignore rules were adjusted carefully

The repo already had broad `dist/` ignores, which initially prevented the vendored `dist` tree from being staged. `.gitignore` was updated so that:

- `frontend/vendor/lectio/node_modules/` stays ignored
- `frontend/vendor/lectio/dist/` is explicitly allowed

This was necessary so the vendored package could actually be committed.

---

## Validation

### Local validation after the CI fix

- `python tools/agent/validate_repo.py --scope frontend`
- `python tools/agent/validate_repo.py --scope all`

Results:

- frontend check: passed
- frontend build: passed
- backend validation: passed
- tooling validation: passed

### GitHub checks after the fix

The PR was rerun and the previously failing checks turned green:

- `backend-quality`: passed
- `frontend-quality`: passed

The merge only happened after these passed.

---

## Tradeoffs Of The Current Temporary Fix

### Advantages

- CI is now self-contained
- no extra repo checkout is required
- no package publishing pipeline is required yet
- builds are reproducible from this repo alone

### Disadvantages

- the repo now contains vendored build output
- PR diffs are much larger and noisier
- vendored Lectio artifacts can drift from the source repo
- updating Lectio requires a manual refresh/copy process

This is why the current state should be treated as a stopgap rather than the ideal long-term solution.

---

## How To Refresh The Vendored Lectio Package Later

If Lectio changes and the temporary approach is kept for a while, the update path is:

1. update/build the sibling Lectio repo
2. refresh `C:\Projects\lectio\dist`
3. copy the new `dist` into `frontend/vendor/lectio/dist`
4. keep `frontend/vendor/lectio/package.json` aligned with the package entrypoints
5. run frontend validation
6. run full repo validation

If contracts changed too, also refresh:

- `backend/contracts/*.json`

from the Lectio export flow.

---

## Recommended Long-Term Replacements

Any of these would be cleaner than committed vendored artifacts:

1. publish Lectio as a real package and install it by version
2. teach CI to check out/build Lectio as part of the workflow
3. move both repos into a workspace/monorepo arrangement

Submodules are technically possible, but they are probably the least friendly workflow here unless there is a strong repo-management reason to choose them.

---

## Where To Start

If someone needs to understand or replace this temporary fix, start here:

1. `frontend/package.json`
2. `frontend/vendor/lectio/package.json`
3. `frontend/vendor/lectio/dist/`
4. `backend/contracts/`
5. `.gitignore`
6. `frontend/package-lock.json`

This handoff should be read together with:

- `docs/project/handoff-shell-platform-restructure.md`

if the reader needs the bigger architectural context around why PR #15 existed in the first place.


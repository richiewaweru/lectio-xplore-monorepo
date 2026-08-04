## Refactor: Package the dirty tree as the source of truth

**Classification**: major  
**Scope**: backend shell + pipeline cutover, frontend native Lectio generation flow, project docs/tooling, archival of legacy specs  
**Behavior changes**:
- Live generation now runs through `backend/src/pipeline/`
- Canonical generation artifact is a JSON `PipelineDocument`
- Frontend generation/viewing now uses native Lectio rendering plus SSE, not polling + HTML/iframe
- Legacy shell services, renderer, and provider paths are removed from the live architecture

### Progress
- [x] Audited the dirty tree and mapped it to coherent architectural slices
- [x] Verified the live runtime shape against existing runbooks and key codepaths
- [x] Fixed the frontend runtime/config drift so the current source of truth validates from a clean checkout
- [x] Ran full repo validation on the final integrated tree
- [x] Recorded what changed, what was removed, and what still needs follow-up
- [x] Prepared this tree for a full push instead of leaving it as undocumented local state

### Validation Evidence

| Command | Result |
| --- | --- |
| `python tools/agent/validate_repo.py --scope all` | Passed |
| `python tools/agent/check_architecture.py --format text` | `No architecture violations found.` |
| `npm test` in `frontend/` | `10 files passed, 29 tests passed` |

## Summary

This branch packages the previously dirty local tree as the new source of truth.

What looked like a large dirty worktree turned out to be a coherent multi-slice architectural migration that had already been implemented across the repo but not fully pushed:

- the backend shell was rebuilt around a standalone `pipeline` engine
- JSON document persistence replaced HTML artifacts
- the public generation API moved to generation/document/event routes
- the frontend moved to native Lectio rendering and SSE hydration
- the app was synced to Lectio's newer runtime surface
- legacy renderer/orchestrator/provider code was removed from the live path
- old top-level specs were archived and replaced by runbooks and current project docs

This handoff records that integrated state so the push is understandable on its own.

## What Changed

| Area | Outcome | Primary files |
| --- | --- | --- |
| Shell + pipeline split | `backend/src/pipeline/` is now the only live generation engine; `backend/src/textbook_agent/` is the shell for auth, profiles, persistence, and transport. | `backend/src/pipeline/`, `backend/src/textbook_agent/interface/api/routes/generation.py`, `backend/src/textbook_agent/interface/api/app.py` |
| Generation persistence | Generations now point to JSON document artifacts and store template/preset/error metadata rather than HTML render outputs. | `backend/src/textbook_agent/domain/entities/generation.py`, `backend/src/textbook_agent/infrastructure/database/models.py`, `backend/src/textbook_agent/infrastructure/repositories/sql_generation_repo.py` |
| Document repository | Added a document repository port + file-backed implementation for canonical `PipelineDocument` save/load. | `backend/src/textbook_agent/domain/ports/document_repository.py`, `backend/src/textbook_agent/infrastructure/repositories/file_document_repo.py` |
| API contract | The live API surface now centers on `/api/v1/generations`, `/document`, `/events`, and `/enhance`; streaming is SSE-backed. | `backend/src/textbook_agent/interface/api/routes/generation.py`, `backend/src/textbook_agent/application/dtos/` |
| Provider/runtime cleanup | Old shell provider implementations were deleted; the pipeline provider registry is the live model selection layer. | `backend/src/pipeline/providers/registry.py`, deleted `backend/src/textbook_agent/infrastructure/providers/` |
| Pipeline engine | Added graph/state/contracts/events/nodes/prompts/types needed for the section-first generation engine and QC/rerender flow. | `backend/src/pipeline/api.py`, `backend/src/pipeline/run.py`, `backend/src/pipeline/graph.py`, `backend/src/pipeline/nodes/`, `backend/src/pipeline/types/` |
| Frontend generation UX | Replaced polling and HTML viewing with document hydration + EventSource streaming + native Lectio rendering. | `frontend/src/lib/api/client.ts`, `frontend/src/routes/textbook/[id]/+page.svelte`, `frontend/src/lib/components/LectioDocumentView.svelte` |
| Template preview/runtime sync | The app now uses Lectio's current runtime surfaces for template preview and shared document theming. | `frontend/src/lib/components/TemplatePreviewOverlay.svelte`, `frontend/src/lib/components/ProfileForm.svelte`, `frontend/src/app.css` |
| Frontend packaging | Restored the frontend manifest/config to match the actual Lectio-native app and validation setup. | `frontend/package.json`, `frontend/package-lock.json`, `frontend/svelte.config.js`, `frontend/vite.config.ts` |
| Architecture/tooling rules | Project docs and the architecture checker now reflect the shell + pipeline split instead of the earlier DDD-only shape. | `agents/project.md`, `tools/agent/check_architecture.py`, `docs/project/ARCHITECTURE.md`, `docs/project/context-summary.yaml` |
| Documentation cleanup | Legacy proposal/spec docs were moved out of the live docs surface and replaced with archived copies plus runbooks/handoffs. | `docs/archive/`, `docs/project/runs/` |

## What Was Intentionally Removed

| Removed area | Reason |
| --- | --- |
| `textbook_agent.application.orchestrator` and old generation use cases | Generation now goes through the pipeline engine instead of the legacy shell orchestration path. |
| Old shell domain entities for textbook/content/diagram/code/QC flow | Those concepts now live in `pipeline` or are no longer the canonical runtime model. |
| HTML renderer and `TextbookViewer` flow | The canonical output is JSON + native Lectio, not rendered HTML artifacts. |
| Polling generation progress helpers | SSE events replaced status polling for the live generation experience. |
| Shell-local provider implementations | The pipeline registry is the authoritative runtime for model selection and provider config. |
| Old top-level proposal/spec docs from `docs/` | They were archived so the live docs surface only reflects the current architecture. |

## Important Fix Applied During Packaging

The codebase itself was largely coherent, but the frontend config had drifted behind the implemented Lectio-native app:

- `frontend/svelte.config.js` had fallen back to `@sveltejs/adapter-auto`
- `frontend/package.json` no longer listed the Lectio/Tailwind/test dependencies the app already used
- `frontend/vite.config.ts` had lost the newer Tailwind/test/manual-chunk setup

This pass restored those files to match the implemented frontend so validation succeeds from a clean checkout rather than only on a machine with stale dependencies installed.

Also added to `.gitignore`:

- `.claude/settings.local.json`

That file is machine-local Codex permissions state, not project source.

## Existing Runbooks That Explain the Slices

Read these first if you need the rationale behind specific parts of the final tree:

1. `docs/project/runs/shell-pipeline-native-lectio-overhaul.md`
2. `docs/project/runs/shell-pipeline-native-lectio-handoff.md`
3. `docs/project/runs/pipeline-engine-phases-1-4.md`
4. `docs/project/runs/pipeline-engine-phases-5-12.md`
5. `docs/project/runs/template-runtime-port-preview-fidelity.md`
6. `docs/project/runs/multi-vendor-model-registry-and-pipeline-provider-envs.md`
7. `docs/project/runs/simulation-smart-frame-handoff.md`

## Start Here Next Time

If you are picking this repo up fresh, start in this order:

1. `backend/src/textbook_agent/interface/api/routes/generation.py`
2. `backend/src/pipeline/run.py`
3. `backend/src/pipeline/contracts.py`
4. `frontend/src/routes/textbook/[id]/+page.svelte`
5. `frontend/src/lib/components/LectioDocumentView.svelte`
6. `frontend/src/lib/components/ProfileForm.svelte`
7. `agents/project.md`

## Remaining Risks / Follow-up

| Area | Follow-up |
| --- | --- |
| Google OAuth local testing | Local sign-in still depends on valid Google OAuth origins and test-user configuration. |
| Template presets in product UI | The frontend is intentionally narrow and currently exposes only the fully wired live preset flow. |
| Simulation generation depth | The simulation frame/templates are in place, but richer end-to-end simulation generation still depends on template/pipeline follow-through. |
| Generated contract refresh | If Lectio contracts change, `backend/contracts/` must still be refreshed from the Lectio export script. |
| Branch granularity | This push intentionally packages a large integrated source-of-truth tree; later cleanup can split future work more narrowly, but this branch is meant to stop the drift between local reality and GitHub. |

## Retired Branch Notes

The older `codex/fix-frontend-build-warnings` branch was reviewed after this source-of-truth push and found to be fully superseded for live code/config.

Its only unique commits were:

- `3fa0c44` `fix(frontend): eliminate build warnings`
- `43b4192` `docs(project): add branch state handoff`

The runtime/config parts of that branch are already represented in this feature branch, and its remaining lockfile delta only downgraded `katex` from `0.16.39` to `0.16.38` without changing the validated runtime behavior. The codex-only handoff was also stale once this integrated handoff existed. That branch can therefore be retired without porting additional code.

## Final State

After this push, GitHub should reflect the actual working architecture of the project rather than a stale pre-cutover shell.

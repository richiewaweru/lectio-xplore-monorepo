# V3 Architecture Audit

Date: 2026-06-18

Objective: Determine whether current `v3` still matches the intended V3 architecture, identify drift introduced by the recent porting work, and define the safest cleanup path before more feature work lands.

## Tracking Checklist
- [x] Read `AGENTS.md`, `agents/ENTRY.md`, `agents/project.md`, refactor workflow, and communication standards.
- [x] Read the original target brief in `C:\Users\richi\Downloads\lectio-v4-codex-goal.md`.
- [x] Read the prior discovery runbook in `docs/project/runs/2026-06-18-v4-lock-discovery.md`.
- [x] Read `docs/project/runs/v3-restructure-runbook.md`.
- [x] Inspect pre-port `v3` tree shape and dependency state from git history.
- [x] Compare current `v3` against the documented baseline.
- [x] Classify current drift into keep, remove, and needs-decision buckets.
- [x] Recommend the cleanup sequence required to restore `v3` to its intended shape.

## Question Being Answered

Did current `v3` drift away from the intended V3 architecture by reintroducing `main`-style planning, pipeline, and LangGraph surfaces?

Answer: yes.

The repo’s own V3 runbook and the pre-port commit shape both show that `v3` was intended to run on the older V3-native architecture centered on:

- `backend/src/generation/v3_studio/`
- `backend/src/v3_blueprint/`
- `backend/src/v3_execution/`
- `backend/src/learning/`

Current `v3` contains a second, newer architecture layered on top of that baseline:

- `backend/src/planning/`
- `backend/src/pipeline/`
- `frontend/src/lib/api/brief.ts`
- `frontend/src/lib/components/studio/TeacherStudioFlow.svelte`
- related LangChain dependency additions

That newer stack matches the ported `main` direction, not the intended V3 baseline.

## Evidence

### 1. Original goal brief matches the older V3 module shape

`C:\Users\richi\Downloads\lectio-v4-codex-goal.md` describes work in terms of:

- `v3_blueprint`
- `v3_execution`
- `generation/v3_studio`
- `learning`

It does not describe the `planning -> pipeline -> generation` architecture used on `main`.

### 2. The prior discovery runbook translated the goal onto the wrong repo shape for `v3`

`docs/project/runs/2026-06-18-v4-lock-discovery.md` mapped the goal onto live backend areas such as:

- `planning`
- `pipeline`
- `generation`
- `core`
- `telemetry`

That mapping made sense for a `main`-style repo, but it conflicts with the historical V3 restructure documented elsewhere in this repository.

### 3. The V3 restructure runbook explicitly removed planning, pipeline, and LangGraph

`docs/project/runs/v3-restructure-runbook.md` records the intended end state for V3:

- Sprint 4 deleted `backend/src/pipeline/`.
- Sprint 4 deleted `backend/src/planning/`.
- Sprint 4 deleted V2 generation entities, repositories, ports, service, recovery, dependencies, and engine port.
- Sprint 4 verification required zero `pipeline.*` and `planning.*` imports.
- Sprint 5 removed `langgraph` from `backend/pyproject.toml`.
- Sprint 5 verification required no `langchain` or `langgraph` in `uv.lock` or `pyproject.toml`.
- Sprint 6 kept the frontend aligned with the V3 studio flow, not a revived brief/planning flow.

This runbook directly contradicts the current branch shape.

### 4. Pre-port git history matches the documented V3-native baseline

Inspection of commit `f02acba` shows:

- `backend/src/generation/v3_studio/` present
- `backend/src/v3_blueprint/` present
- `backend/src/v3_execution/` present
- `backend/src/learning/` present
- no `langchain-core` dependency in `backend/pyproject.toml`

This confirms that the documented restructure was not theoretical. It existed in the branch history.

### 5. Recent commits reintroduced the removed architecture

Recent branch history shows:

- `9fbef28 refactor(pipeline): land v4 lock flow on v3`
- `47fd9de fix(backend): add langchain core runtime dependency`

The first commit reintroduced large `planning` and `pipeline` trees plus a new frontend brief/planning flow. The second commit added `langchain-core` only because the first commit had already restored that stack.

### 6. Frontend inspection shows two competing studio architectures

Current frontend state is split:

- `frontend/src/routes/studio/+page.svelte` is the V3-native flow using `$lib/api/v3` and `/api/v1/v3/*`.
- `frontend/src/lib/components/studio/TeacherStudioFlow.svelte` is a separate planning flow using `$lib/api/brief` and `/api/v1/brief/stream`.

That duality is a strong sign of architectural drift rather than a coherent V3 design.

## Classification

### Keep

These areas match the intended V3 baseline and should remain the foundation:

- `backend/src/generation/v3_studio/**`
- `backend/src/v3_blueprint/**`
- `backend/src/v3_execution/**`
- `backend/src/learning/**`
- `frontend/src/routes/studio/+page.svelte`
- `frontend/src/lib/api/v3.ts`
- V3-oriented dashboard, builder, print, booklet, supplement, and document flows that rely on `/api/v1/v3/*`

### Remove

These additions represent the revived `main` architecture and should not remain on `v3` unless a later decision intentionally re-adopts them:

- `backend/src/pipeline/**`
- `backend/src/planning/**`
- `backend/src/generation/service.py`
- `backend/src/generation/dependencies.py`
- `backend/src/core/ports/generation_engine.py`
- V2-style generation DTO/entity/port/repository layers reintroduced by `9fbef28`
- LangChain dependency additions in `backend/pyproject.toml`
- matching lockfile changes in `backend/uv.lock`
- `frontend/src/lib/api/brief.ts`
- `frontend/src/lib/components/studio/TeacherStudioFlow.svelte`
- `frontend/src/lib/components/studio/IntentForm.svelte`
- `frontend/src/lib/components/studio/PlanStream.svelte`
- `frontend/src/lib/components/studio/PlanReview.svelte`
- `frontend/src/lib/components/studio/GenerationView.svelte`

### Needs Decision

These items may contain useful product ideas, but they should be judged separately from the imported architecture:

- any teacher-facing linear planning UX that users like from the newer flow
- any telemetry changes that are useful outside planning/pipeline
- any route or payload changes that can be reimplemented on top of V3-native services
- selective bug fixes bundled inside the port commits that are not inherently tied to `planning` or `pipeline`

The default recommendation is not to preserve these by default inside the revived architecture. If they are worth keeping, they should be reimplemented on top of V3-native modules.

## Recommended Cleanup Path

1. Treat `9fbef28` as architectural drift, not baseline.
2. Remove the reintroduced backend `planning` and `pipeline` trees.
3. Remove frontend brief/planning flow modules that depend on `/api/v1/brief/*`.
4. Remove `langchain-core` and regenerate the backend lockfile after the planning/pipeline imports are gone.
5. Re-run backend and frontend validation against the V3-native path only.
6. Reassess the original goal brief against the restored V3 baseline before adding new product work.

## Practical Implementation Note

The safest restoration approach is to compare current `v3` against the pre-port baseline and intentionally remove drift, not continue patching the imported `main` architecture. In practice that likely means reverting or manually undoing the surfaces introduced by:

- `9fbef28 refactor(pipeline): land v4 lock flow on v3`
- `47fd9de fix(backend): add langchain core runtime dependency`

with care for any unrelated fixes that should be preserved.

## Conclusion

Current `v3` is not fully aligned with the intended V3 branch shape.

The branch already contains the correct V3-native architecture, but it also contains a second imported architecture from `main`. The right next move is cleanup and consolidation around the V3-native stack before further implementation work continues.

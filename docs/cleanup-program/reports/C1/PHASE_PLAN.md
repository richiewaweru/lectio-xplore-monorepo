# C1 PHASE PLAN — Canonical Unit-Path Wiring

Starting: branch `refactor/domain-ownership`, SHA `25db4a7`, dirty domain-refactor tree.

## Scope (this phase only)

1. **Admission fix** — `generation/path_preparation.py:initialise_path_generation` accept + persist `native_whole_lesson` / `path_plan_raw` into chunked state.
2. **`application/unit_lesson/`** — thin re-export of `prepare_path_lesson` + `PathPreparationBlocked`; `curriculum.routes` imports application as canonical name.
3. **`app.py` rewire** — import `curriculum.routes` / `curriculum.compatibility`, `infra.config` / `infra.health` / `infra.telemetry` / `infra.database` / `infra.logging` / `print.rendering.pdf.runtime` / `print.generation.whole_lesson.worker` where shims exist. Keep mounting the same routers (including v3). Auth/profile/prompts remain `core.routes.*` (still live under core).
4. **Frontend restore** — mechanical string replace to disk/backend paths (`/studio`, `/builder`, `$lib/learn/authoring/builder`, `$lib/print/components/studio`, `/api/v1/builder`, `/api/v1/auth`, `/settings`).

## Out of scope
Builder PDF extract, v3_studio Print HTTP extract, deletions, README/docs cleanup.

## Verify
`pnpm program:domain-guards`; focused pytest path/units/builder; focused frontend vitest routing/auth/builder/studio.

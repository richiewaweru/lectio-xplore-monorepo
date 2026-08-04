# Project Docs

Live project-specific documentation for the core + generation + planning + pipeline + native Lectio runtime.

## Contents

| Doc | What it covers |
| --- | --- |
| [agent-context.md](agent-context.md) | Current source-of-truth runtime and operational context |
| [ARCHITECTURE.md](ARCHITECTURE.md) | DDD layer rules and architecture guard |
| [SETUP.md](SETUP.md) | Install commands and project-local tools |
| [DEVELOPMENT_WORKFLOW.md](DEVELOPMENT_WORKFLOW.md) | How CI and validation work |
| [SCHEMAS.md](SCHEMAS.md) | Current public and internal data contracts |
| [MODEL_SLOTS_AND_PROVIDERS.md](MODEL_SLOTS_AND_PROVIDERS.md) | As-built model slots, `load_profiles`, env vars, transports, SSE/cost |
| [handoff-shell-platform-restructure.md](handoff-shell-platform-restructure.md) | Detailed handoff for the shell/platform restructure merged in PR #15 |
| [handoff-lectio-ci-temporary-vendoring.md](handoff-lectio-ci-temporary-vendoring.md) | Detailed handoff for the temporary Lectio/contracts CI self-containment fix |
| [context-summary.yaml](context-summary.yaml) | Machine-readable project config (used by `tools/agent/` scripts) |
| [stage-packs/](stage-packs/) | Stage-specific operating notes for agents |
| [runs/](runs/) | Tracking checklists and runbooks |

## Relationship to `agents/`

- `agents/` has the universal standards, workflows, and project config in `agents/project.md`.
- This directory has project-specific docs that go deeper: architecture details, setup instructions, CI workflow.
- `agents/project.md` is the quick reference. These docs are the detailed reference.

## Archive Note

`docs/v0.1.0/` is kept as a historical snapshot. Current implementation details live here under `docs/project/`.

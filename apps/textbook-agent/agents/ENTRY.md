# Agent Entry Point

Read this file first in every new session.

## Before You Start

1. Read this file completely.
2. Read `agents/project.md` for this project's specific rules and commands.
3. Read the project's main config (`CLAUDE.md`, `README.md`, or equivalent) if you haven't already.
4. Identify what you've been asked to do and pick the right workflow below.

## Pick Your Workflow

| Task type | Read this first |
| --- | --- |
| New feature | `agents/workflows/feature.md` |
| Bug fix | `agents/workflows/bugfix.md` |
| Refactor or migration | `agents/workflows/refactor.md` |
| Release | `agents/workflows/release.md` |

Each workflow includes a **mandatory tracking checklist**. Copy it to your working notes, PR body, or a runbook file. Update it as you work.

## Standards That Always Apply

All files in `agents/standards/` apply to every task. The most critical rules:

- **Scope changes tightly.** Make the smallest coherent change that delivers the ask. Read `agents/standards/change-management.md`.
- **Test what you change.** Every behavioral change needs a test. Read `agents/standards/testing.md`.
- **Respect architectural boundaries.** Don't introduce forbidden dependencies. Read `agents/standards/architecture.md`.
- **Communicate clearly.** Commit messages explain why, PR descriptions explain what and why. Read `agents/standards/communication.md`.

Read the full standard before doing anything in that area. When a standard conflicts with project-specific rules in `project.md`, project rules win.

## Quality Gates

Before marking any work as complete:

- All relevant tests pass
- Linting is clean
- Changes are scoped and coherent (one logical change per commit)
- Commit messages follow `agents/standards/communication.md`
- Self-reviewed against `agents/standards/review.md`

## Mandatory Tracking

Every multi-step task must have a visible progress checklist. This can live in:
- The PR body
- A runbook file in `docs/project/runs/`
- Your working notes (if no PR yet)

Don't mark work complete without validation evidence. Don't skip checklist steps.

## Multi-Agent Work

If you are coordinating with other agents or delegating subtasks, read `agents/coordination/` first.

Key rules:
- One orchestrator owns the final deliverable and tracking checklist
- Subagents work within explicit scope and report back to the orchestrator
- Every handoff includes: what changed, what's validated, what's left

## Stop Conditions

- Do not start implementation before understanding the full scope
- Do not mark work ready without validation evidence
- Do not bypass protected branches or skip required checks
- If you're unsure about scope or approach, ask before coding

# AGENTS

> Read this file first in every new agent session.

## Entry Point

Read `agents/ENTRY.md` for the full agent onboarding sequence, workflow routing, quality gates, and coordination rules.

## Quick Reference

| Need to... | Read this |
| --- | --- |
| Understand project rules | `agents/project.md` |
| Deliver a feature | `agents/workflows/feature.md` |
| Fix a bug | `agents/workflows/bugfix.md` |
| Refactor or migrate | `agents/workflows/refactor.md` |
| Prepare a release | `agents/workflows/release.md` |
| Coordinate with other agents | `agents/coordination/` |
| Review code quality rules | `agents/standards/` |

## Non-Negotiable Rules

- Every multi-step task must have a visible tracking checklist.
- Run validation before marking work complete.
- Respect architectural boundaries declared in `agents/project.md`.
- Follow commit conventions in `agents/standards/communication.md`.

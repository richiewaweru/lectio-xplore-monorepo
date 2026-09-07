# Portable Agent Standards

A drop-in directory of development standards, workflows, and coordination patterns for AI coding agents. Language-agnostic, framework-agnostic, agent-agnostic.

## What This Is

`agents/` is a curated set of markdown files that any AI coding agent (Claude, Codex, Cursor, GPT, etc.) can read to understand how to work on your project. It contains:

- **Standards** -- opinionated rules about code quality, testing, architecture, communication
- **Workflows** -- step-by-step playbooks for common tasks (features, bugfixes, refactors, releases)
- **Prompts** -- focused instructions for AI code review
- **Coordination** -- patterns for multi-agent and multi-session work

There are no scripts to run, no templates to render, no dependencies to install. Agents read markdown and follow instructions.

## Quick Start (New Project)

```bash
# 1. Copy the layer into your project
cp -r agents/ ~/your-project/agents/

# 2. Fill in project-specific rules
# Edit agents/project.md -- overview, architecture, validation commands, conventions

# 3. Create the root bridge file
cp agents/_templates/AGENTS.md ~/your-project/AGENTS.md

# 4. Wire your agent config (pick one or more)
```

### Agent Config Wiring

Each agent platform has a file it reads automatically. Add one line to connect it to the layer:

| Agent | Config file | What to add |
| --- | --- | --- |
| **Claude Code** | `CLAUDE.md` | `## Agent Standards\nRead agents/ENTRY.md for development standards, workflows, and quality gates.` |
| **Codex** | `AGENTS.md` | Already reads it natively -- just have it point to `agents/ENTRY.md` |
| **Cursor** | `.cursorrules` | `Read agents/ENTRY.md for development standards, workflows, and quality gates.` |
| **GitHub Copilot** | `.github/copilot-instructions.md` | Same one-liner |
| **Any other agent** | System prompt or context | Include `agents/ENTRY.md` content |

### What Agents See

```
Agent starts session
  → reads its config file (CLAUDE.md, .cursorrules, etc.)
  → follows pointer to agents/ENTRY.md
  → ENTRY.md routes to: project.md (rules), workflows/ (how to work), standards/ (quality)
  → agent picks the right workflow, creates a tracking checklist, starts working
```

### Session Continuity

Tracking checklists in `docs/project/runs/` (or PR bodies) provide continuity between sessions. A new agent reads the last checklist to see where things stand.

That's it. Three files to touch, zero dependencies to install.

## Directory Layout

```
agents/
  README.md              # You are here -- system overview for humans
  ENTRY.md               # Single entry point every agent reads first
  project.md             # Project-specific config (the only file you edit per-project)

  standards/             # Universal development rules
    code-quality.md      # Writing good code
    change-management.md # Scoping and sequencing changes
    testing.md           # Testing expectations
    architecture.md      # Respecting boundaries
    review.md            # Self-review and PR review
    communication.md     # Commits, PRs, handoffs

  prompts/               # AI review prompt fragments
    bug-risk.md          # Behavioral regressions
    architecture-compliance.md  # Boundary violations
    test-gap.md          # Missing test coverage

  workflows/             # Task playbooks with mandatory checklists
    feature.md           # Deliver a new feature
    bugfix.md            # Fix a bug
    refactor.md          # Structural refactor or migration
    release.md           # Prepare a release

  coordination/          # Multi-agent patterns
    topology.md          # Orchestrator/worker model
    delegation.md        # Delegation and handoff between agents

  _templates/            # Copy-paste ready files for new project setup
    AGENTS.md            # Root bridge file -- copy to your project root
```

## Design Philosophy

1. **Files agents read, not code agents run.** The value is well-structured instructions, not code generation.
2. **Convention over configuration.** A small `project.md` over a sprawling YAML schema.
3. **Standards are the core product.** Everything else supports them.
4. **Progressive complexity.** Solo agent reads 2-3 files. Multi-agent orchestration reads more.
5. **Mandatory tracking.** Every multi-step task must have a visible checklist. But it's a markdown checklist, not a validated artifact.

## Updating Standards

This directory is meant to evolve. As you learn what works and what doesn't:

- Update standards with new rules or refine existing ones
- Add workflow steps you keep needing
- Remove rules that don't earn their keep
- Keep `project.md` current with your project's actual conventions

The standards should reflect your real experience, not theoretical best practices.

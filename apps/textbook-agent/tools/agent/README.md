<!-- generated-by: agents/scripts/bootstrap_project.py -->
# Project Agent Tools

This directory is the generated, project-local execution layer for `Textbook Generation Agent`.

## Boundary
- `agents/` owns policy, templates, prompts, scaffold generation, and runbook or PR contract validation.
- `tools/agent/` owns repo-specific execution entrypoints used by local development and GitHub workflows.

## Current Entry Points
- `python tools/agent/validate_repo.py --scope all`
- `python tools/agent/check_architecture.py --format text`
- `python tools/agent/extract_release_notes.py --version v0.1.0`
- `python tools/agent/run_ai_review.py --output ai-review.md`

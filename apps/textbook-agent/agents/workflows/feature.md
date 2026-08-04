# Feature Delivery Workflow

Step-by-step playbook for delivering a new feature. Follow these steps in order.

## 1. Understand the Request

- Read the task description carefully. What is actually being asked for?
- Identify which subsystems are affected (backend, frontend, both, infrastructure).
- Read `agents/standards/change-management.md` -- is this minor or major?
- If major, consider whether it should be split into multiple PRs.

## 2. Read the Context

- Read `agents/project.md` for architecture rules and validation commands.
- Read the relevant source code. Understand existing patterns before writing new code.
- Check recent commits (`git log --oneline -20`) for related changes or ongoing work.
- If this builds on or conflicts with in-progress work, coordinate before coding.

## 3. Create Your Tracking Checklist

Copy this to your PR body or a runbook file in `docs/project/runs/`:

```markdown
## Feature: [title]

**Classification**: [minor/major]
**Subsystems**: [backend/frontend/both]

### Progress
- [ ] Understood requirements and identified scope
- [ ] Read relevant source code and project rules
- [ ] Implemented the change
- [ ] Wrote tests for new behavior
- [ ] Ran validation (backend: ruff + pytest, frontend: check + build)
- [ ] Self-reviewed against agents/standards/review.md
- [ ] Wrote commit message(s) following agents/standards/communication.md
- [ ] Updated PR description with summary, validation evidence, risks
- [ ] Noted any follow-up work or open questions

### Validation Evidence
<!-- Paste test output, linting results, etc. -->

### Risks and Follow-up
<!-- What could go wrong? What's left for later? -->
```

## 4. Implement

- Follow `agents/standards/code-quality.md`.
- Make the smallest coherent change that delivers the feature.
- Write tests alongside the implementation, not after.
- Respect architectural boundaries (see `agents/project.md`).
- If scope expands during implementation, stop and reassess. Don't silently grow the change.

## 5. Validate

- Run all validation commands from `agents/project.md`.
- Verify tests pass and cover the new behavior.
- Run linting and type-checking.
- Self-review your diff: read it as if someone else wrote it.
- Check for accidental changes, debug logging, unrelated modifications.

## 6. Communicate

- Write commit messages following `agents/standards/communication.md`.
- Update your tracking checklist with validation evidence.
- Write a PR description that explains what changed, why, and how to verify.
- Note any risks, rollback considerations, or follow-up work.

## 7. Done Criteria

Your feature is ready when:
- [ ] All tracking checklist items are checked
- [ ] All automated checks pass
- [ ] Validation evidence is recorded
- [ ] PR description is complete
- [ ] No unresolved blockers or open questions

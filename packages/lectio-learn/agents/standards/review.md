# Review

Rules for reviewing your own work and others'. Good review catches bugs before they ship and keeps the codebase healthy.

## Self-Review Before Submitting

Before asking for review or marking work ready:

1. **Read your own diff.** Look at every changed line as if someone else wrote it. Does it make sense?
2. **Check for accidental changes.** Debug logging, commented-out code, formatting-only changes to files you didn't mean to touch.
3. **Verify the tests.** Do they test the actual behavioral change? Are assertions meaningful (not just "didn't throw")?
4. **Check boundary compliance.** Run architecture validation if available. Verify no forbidden imports snuck in.
5. **Read the commit message.** Does it explain *why* the change was made, not just *what* changed?

## What to Look For in Review

### Correctness
- Does the code do what it claims to do?
- Are there edge cases that aren't handled?
- Could any input cause unexpected behavior?
- Are error paths handled correctly?

### Clarity
- Can you understand the code without the PR description?
- Are names descriptive and consistent?
- Is the logic straightforward, or does it require mental gymnastics?

### Scope
- Does the change match what was asked for?
- Is there unrelated cleanup bundled in?
- Could this be split into smaller, independent changes?

### Architecture
- Does it respect declared boundaries?
- Are new dependencies appropriate?
- Does it follow existing patterns, or introduce a new pattern without justification?

## Deterministic vs. Advisory Review

**Deterministic gates** are automated checks (linting, type-checking, test suites, architecture guards). These are authoritative. If they fail, the code is not ready. Don't merge with failing checks.

**Advisory review** (including AI-generated review) is informational. Findings must be triaged explicitly:
- Fix it if it's valid
- Note it as follow-up if it's valid but out of scope
- Dismiss it if it's wrong, with a brief explanation

Never ignore advisory findings without triaging them.

## Review Prompts

For AI-assisted review, focused prompts produce better results than generic "review this code":
- `agents/prompts/bug-risk.md` -- behavioral regressions and correctness issues
- `agents/prompts/architecture-compliance.md` -- boundary and dependency violations
- `agents/prompts/test-gap.md` -- missing or weak test coverage
- `agents/prompts/workflow-compliance.md` -- runbook, CI, and delivery-process issues

Use these when reviewing diffs. They're short and focused.

## What Makes a PR Mergeable

A PR is ready to merge when:
- [ ] All automated checks pass (CI, linting, type-checking, tests)
- [ ] The change is scoped correctly (one logical change)
- [ ] The PR description explains the why and the what
- [ ] Validation evidence exists (test output, manual verification)
- [ ] No unresolved review findings
- [ ] The tracking checklist is complete (see workflow docs)

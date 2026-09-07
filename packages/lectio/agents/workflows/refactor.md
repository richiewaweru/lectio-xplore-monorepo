# Refactor / Migration Workflow

Step-by-step playbook for structural changes: refactoring code, migrating interfaces, reorganizing modules, changing architectural patterns. These changes are higher risk because they touch foundations.

## 1. Define the Scope

- What exactly is being restructured and why?
- What are the boundaries of the change? Which modules/layers are affected?
- What should NOT change? (Behavior, external interfaces, API contracts.)
- Is this a single PR or should it be phased?

Read `agents/standards/change-management.md` -- structural changes are almost always major.

## 2. Understand the Current State

- Read all code that will be moved, renamed, or restructured.
- Map the current dependency graph: what depends on what you're changing?
- Check for indirect consumers (tests, scripts, configs, documentation).
- Run validation before starting. Establish a known-good baseline.

## 3. Create Your Tracking Checklist

Copy this to your PR body or a runbook file:

```markdown
## Refactor: [title]

**Classification**: major
**Scope**: [which modules/layers are affected]
**Behavior changes**: none (or list them)

### Progress
- [ ] Documented scope and interfaces affected
- [ ] Mapped current dependencies
- [ ] Established baseline (all tests passing before changes)
- [ ] Implemented structural change
- [ ] Verified all existing tests still pass (behavior preserved)
- [ ] Added tests for any new interfaces
- [ ] Ran full validation (backend + frontend)
- [ ] Updated documentation if architecture rules changed
- [ ] Self-reviewed against agents/standards/architecture.md

### Validation Evidence
<!-- Show before/after test results -->

### Risks and Follow-up
<!-- What consumers might break? What docs need updating? -->
```

## 4. Implement

- Move in small, verifiable steps. Run tests after each step.
- Preserve behavior. If a test breaks, the refactor introduced a bug -- fix it before continuing.
- Don't combine structural changes with behavioral changes in the same commit. Structure first, behavior second.
- Update imports, references, and configuration as you go. Don't leave broken references.
- If you're changing architecture rules, update `agents/project.md`.

## 5. Validate

- Run the full validation suite -- not just the subsystem you changed.
- Compare test results with your baseline. Same pass count, no new failures.
- Run architecture validation if available (`tools/agent/check_architecture.py`).
- Check for orphaned code: modules that are no longer imported, tests that no longer test anything.

## 6. Communicate

- Commit messages should clearly describe the structural change: `refactor(domain): extract LLM port interface from base provider`
- PR description must explicitly call out: what was restructured, why, what behavior is preserved, what (if anything) changed.
- If architecture rules changed, note it prominently.

## 7. Done Criteria

- [ ] All existing tests pass (behavior preserved)
- [ ] No orphaned code or broken references
- [ ] Architecture rules in `agents/project.md` are current
- [ ] Full validation passes (not just the affected subsystem)
- [ ] Tracking checklist is complete with validation evidence

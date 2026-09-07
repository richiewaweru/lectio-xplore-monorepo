# Release Workflow

Step-by-step playbook for preparing and cutting a release. A release freezes the current state and creates a versioned snapshot.

## 1. Prepare

- Confirm all in-progress work is either merged or deferred.
- Check that `main` (or your release branch) is in a clean, passing state.
- Review the changelog or commit history since the last release to understand what's included.
- Decide the version number following SemVer:
  - **Patch** (0.1.1): bug fixes only
  - **Minor** (0.2.0): new features, backwards compatible
  - **Major** (1.0.0): breaking changes

## 2. Create Your Tracking Checklist

Copy this to your PR body or a runbook file:

```markdown
## Release: v[X.Y.Z]

### Progress
- [ ] All in-progress work merged or deferred
- [ ] Main branch is clean and all checks pass
- [ ] Full validation suite passes (backend + frontend)
- [ ] CHANGELOG.md updated with release notes
- [ ] Version bumped in relevant config files
- [ ] Snapshot docs created in docs/v[X.Y.Z]/ (if applicable)
- [ ] Release tag created
- [ ] Handoff notes written

### Validation Evidence
<!-- Full test output, build results -->

### Release Notes Summary
<!-- Key changes in this release -->
```

## 3. Validate Everything

- Run the full validation suite from `agents/project.md`. Every check must pass.
- This is not the time to discover test failures. If something fails, fix it before releasing.
- Verify the build artifacts are correct (frontend builds, backend packages, etc.).

## 4. Update Documentation

- Update `CHANGELOG.md` with a summary of changes since the last release.
- Group by: Features, Bug Fixes, Breaking Changes, Other.
- Create snapshot docs under `docs/vX.Y.Z/` if the project uses versioned documentation.
- Update version numbers in config files (`pyproject.toml`, `package.json`, etc.).

## 5. Tag and Ship

- Create the release tag: `git tag vX.Y.Z`
- Push the tag: `git push origin vX.Y.Z`
- If the project uses GitHub Releases, create one with the changelog content.

## 6. Handoff

Write a handoff note (in the tracking checklist or a separate file):

- What's in this release (key features, fixes)
- Known issues or limitations
- What's planned next
- Any deployment or migration steps required

## 7. Done Criteria

- [ ] Full validation passes
- [ ] CHANGELOG is current
- [ ] Version is bumped
- [ ] Tag is created and pushed
- [ ] Snapshot docs exist (if applicable)
- [ ] Handoff notes are complete

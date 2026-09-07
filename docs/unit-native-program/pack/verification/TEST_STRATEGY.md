# Test strategy and command discovery

## Classes of proof
1. Package: schemas, metadata/export parity, renderer/evaluator fixtures and readiness.
2. Contract: stage packet isolation, source references, revision/hash and candidate legality.
3. Integration: real DB and production services; external provider mocking explicitly disclosed.
4. Live: configured real providers, actual UI/API product routes, rendered inspection and DB persistence.

A lower class does not substitute for a higher class. Mock plans may test an executor but cannot prove planning quality. D6 tests remain useful regression coverage; new gates must remove prepared-plan substitution.

## Command map
Existing root hints include pnpm page:test, pnpm page:check, pnpm app:check and pnpm program:domain-guards. Backend usually runs with uv; inspect package.json, pyproject.toml, CI and workspace scripts at P00 to confirm exact commands. Never report these hints as commands actually run.
Record cwd, command, environment names (not secrets), exit code, counts and output artifact for each gate. Use test DB fixtures and existing migration tooling. Do not reset an unknown DATABASE_URL.
If a command is absent, record the verified replacement. Maintain COMMAND_MAP.md with owner, purpose and command.

## Required behavioural tests
- Export changed capability source → all consumers see same updated metadata/hash; old pinned release unchanged.
- Unknown intent/action, invalid IDs and unavailable capabilities fail.
- Ordered repeated slot/component instances round-trip without loss.
- Same shared plan feeds both paths; no fixture replacement.
- Required unsupported interaction causes explicit incompatibility.
- Correct/incorrect/partial/empty/duplicate/unknown responses; scoring parity across runtimes.
- Source task ownership and answer visibility preserved.
- Revision change, concurrent realization creation, concurrent submissions, duplicate publish, stale lease and restart.
- Teacher edit survival and native sibling isolation.
- Publish rejects invalid config and false source provenance.
- Auth/session/assignment/evidence scoping and passive completion.
- Actual Print route, visual rendering and PDF process termination.

## Isolation tests
Inject sentinel IDs in excluded catalogue entries, sibling schemas, unrelated Unit data and future task payloads. Inspect actual serialized provider requests, including tool schema and prompt text. Excluded sentinels must be absent; legitimate approved answer data must remain available to its own activity writer.
Inspect provider output schema: code-owned fields should not be emitted for model rewriting.

## Evidence integrity
Test fixture names and production data names must differ. Store mocks and live evidence in separate directories. Screenshot-only evidence is insufficient for persistence; DB-only evidence is insufficient for UI behaviour. Record IDs/hashes connecting both.
No passing snapshots that merely freeze known wrong scoring or over-broad analytics. Assert intended behaviour.

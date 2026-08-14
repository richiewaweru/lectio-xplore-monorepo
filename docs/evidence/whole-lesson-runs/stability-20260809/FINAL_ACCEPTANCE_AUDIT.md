# Final acceptance audit

Date: 2026-08-12
Authority: `PLAN.md` and the supplied XPLORE stability goal.

## Verified current-product contracts

| Requirement | Current evidence |
| --- | --- |
| Native Home/New unit entry | Authenticated `/units` replay; native New unit form; frontend routing tests |
| No active Builder fallback | Native-only routing/quarantine tests; architecture validator reports no violations |
| Native V2 viewer/PDF selection | Backend PDF/export suites and frontend viewer/print suites |
| Truthful retry/status UI | Native status/retry tests; authenticated Water Cycle viewer shows `Retry visuals` |
| Visual handoff/topology validation | 69 focused topology/recovery/dispatch/renderer/compositor/execution tests; full backend suite includes these |
| Authenticated native print | Browser replay reaches the pending-visual guard; shared `apiFetch` token precedence tests |
| Persistence/reload fencing | Document fencing/reload/visual invalidation tests; deterministic hash gates |
| Worker lease/fencing | 87 lease/reclaim/fencing tests; `RECOVERY_RUN_5C254377.md` records a real reclaim |
| Telemetry plumbing | Full backend suite, telemetry-focused tests, and attributed live diagnostic rows |
| Repository health | Backend 1,080 tests; frontend 81 files/341 tests; Svelte 0/0; build passed; tooling 8 passed |

The latest provider-free visual-core rerun passed **69 tests** with one existing
Pydantic warning; Ruff and Python compilation also passed. The dispatcher is
wired to route flagged internal assets through topology recovery without an
xAI call, and the topology recovery/renderer boundary is covered by focused
tests.

The active lesson prompt verifier also passes (`prompt_checksums=ok`, v2 active,
SHA `2ccc4c7b...`), and the repository architecture checker reports no
violations. These checks validate the current source boundary only; they do not
replace the missing live-provider acceptance evidence below.

The final provider-free boundary rerun passed **84 focused tests** with one
existing Pydantic warning; architecture validation again reported no
violations. All topology/planner/recovery/renderer/compositor test modules are
present, and frontend/backend health probes returned HTTP 200.

Source review confirms the recovery path is fail-closed and isolated: topology
identity mismatches stop before rendering, source assets are addressed by
internal key, topology persistence is atomic and resumable, deterministic
rendering precedes completion, and accepted output uses the existing visual
revision/hash fencing. This is implementation evidence only; it does not count
as a live-provider acceptance run.

The review also closed a QC boundary gap: topology recovery now applies a
fail-closed deterministic asset/topology check when no injected model-QC hook is
provided, and rejects unidentified render output before completion. The
affected visual boundary rerun passed **70 tests**, and Ruff passed.

A further resume-integrity check now revalidates persisted topology labels,
evidence, and graph structure against the current authoritative source before
rendering; malformed resumed checkpoints fail closed. Recovery regressions now
pass **7 tests**, with Ruff clean.

The injected-QC branch is also fail-closed: a flagged topology verdict cannot
invoke document completion. The final compact visual boundary rerun passed
**72 tests** with one existing Pydantic warning.

Recovery now also rejects hash-only render metadata; a concrete `src` or `svg`
is required before visual completion. The expanded provider-free visual suite
passed **73 tests** with one existing Pydantic warning.

Final source-level hygiene check: topology/recovery/renderer/compositor tests
passed **31 tests**, Ruff and `git diff --check` passed for the changed recovery
files, and frontend/backend health probes returned HTTP 200.

Recovery test doubles are now scoped with `monkeypatch`, preventing repository
method overrides from leaking between tests; the isolated recovery suite remains
green at **9 passed**.

Injected QC verdicts are now schema-checked: `accept`/`ready` is required,
flagged/rejected output remains retryable, and null or unsupported verdicts fail
closed. The compact visual boundary rerun passed **74 tests** with one existing
Pydantic warning.

Dispatch now filters topology-recovery blocks by both top-level and nested asset
request IDs, preventing an asset-only request from falling through to normal
provider execution. The compact visual boundary rerun passed **75 tests**; the
recovery suite passed **11 tests**, with Ruff clean.

Final source/runtime hygiene check: Ruff, `git diff --check`, and architecture
validation all passed; the focused visual suite passed **75 tests** with one
existing Pydantic warning; frontend/backend health probes returned HTTP 200.

## Required evidence still missing or not accepted

These cannot be inferred from deterministic tests or the flagged diagnostic run:

1. A live visual run with provider asset accepted by QC and persisted as ready.
2. Visual-only retry ending in accepted ready state with no upstream rerun.
3. Teacher and student PDFs from that accepted live visual run, with visual present
   and answer visibility verified.
4. Four new browser-driven final matrix runs through the normal UI.
5. A complete live latency/telemetry manifest for each final matrix run.

## Current verdict

`NOT YET STABLE` under `PLAN.md`. The implementation is deterministic-green and
the active UI is native-only, but the live-provider and final-matrix acceptance
requirements remain open. No provider call or generation mutation was made by
this audit.

## Next authorized live run

Use `LIVE_ACCEPTANCE_RUNBOOK.md` for the five targeted proofs and the four-run
matrix. The runbook includes the required stop gates, telemetry fields, PDF/
reload evidence, and the rule that no hidden endpoint or database progression is
allowed.

# Overnight Report — Stable, Resumable Generation + PDF Export

Status: in progress. This report is intentionally incomplete until authenticated browser runs and the four-lesson acceptance matrix are complete.

## 1. Matrix status

| Lesson | Native UI run | Viewer evidence | Teacher PDF | Student PDF | Evidence |
|---|---|---|---|---|---|
| Grade 4 Science — Why Plants Need Light to Make Food | Not run | Missing | Missing | Missing | — |
| Grade 6 Mathematics — Understanding Equivalent Fractions | Not run | Missing | Missing | Missing | — |
| Grade 8 Economics — How Supply and Demand Affect Price | Not run | Missing | Missing | Missing | — |
| Grade 7 English — Distinguishing a Claim from Supporting Evidence | Not run | Missing | Missing | Missing | — |

The local frontend is reachable at `http://127.0.0.1:5173`; the in-app browser
currently reaches the Google sign-in screen and has no existing authenticated tab
or session. No acceptance evidence has been manufactured.

## 2. What was broken

Proven defects:

- Constrained DeepSeek nodes still enabled provider reasoning, increasing latency and allowing empty reasoning-only responses.
- Validation failures had no repair prompt; retries could replay the same invalid response.
- Truncated completions were not retryable.
- Network retry delay was linear and omitted several transport exception classes.
- The v3 lane budget default was exactly aligned with two call timeouts, leaving no retry/save headroom.
- Answer-key concurrency was hard-coded to one.
- Lane checkpoint lookup/save errors were swallowed.
- On resume, persisted prose/questions were skipped but not rehydrated into the execution result; the runner also marked both stages complete unconditionally.
- Local `.env` had an earlier Docker PDF hostname before the native localhost value; configuration loading can preserve the earlier value.

## 3. What changed

- `backend/src/core/llm/runner.py`: repair attempts, truncation retry, transport retry classification, exponential jittered network backoff, repair telemetry events.
- `backend/src/v3_execution/llm_helpers.py`: explicit node timeout/retry policy and one schema repair attempt.
- `backend/src/v3_execution/config/models.py`: reasoning disabled for constrained nodes and env-overridable per-node reasoning.
- `backend/src/v3_execution/config/concurrency.py`: 420-second lane default, configurable answer-key concurrency, budget diagnostic.
- `backend/src/v3_execution/runtime/lanes.py`: checkpoint hydration, independent stage completion, failure classification, loud persistence logging.
- `backend/src/v3_execution/runtime/runner.py`: stage-aware completion, visual checkpoint logging, and an explicit failed-lane/incomplete-section completion gate.
- `backend/src/v3_execution/booklet_status.py` and `backend/src/core/config.py`: configurable `V3_MAX_FAILED_LANE_FRACTION` (default `0.0`) prevents partial or failed lane output from becoming a final-ready booklet.
- `backend/src/generation/v3_studio/generation_writer.py`: persisted/reloaded status derivation now applies the same incomplete-section gate, preventing a document reload from reviving an incomplete pack as final.
- `backend/src/v3_blueprint/planning/persistence.py`: single-step checkpoint payload loading.
- `backend/src/core/config.py` and `.env.example`: 8k/16k/24k slot ceilings and 32k absolute fallback.
- Frontend recovery paths were inspected; no additional UI change was required in this slice.

Commits: `841f0d4`, `4e0fc0c`, `a0980d0`, `0603ba3`, `b0cb871`.

Validation: architecture gate passed with no violations; backend Ruff passed; the
full backend suite passes 1,158 tests (one existing warning about a Pydantic field
name). The focused frontend recovery suite passes 36 tests. The complete frontend
suite was not used as a gate because Vitest worker teardown stopped emitting; the
focused suite completed cleanly.
The completeness-gate status tests pass (11 tests), and the execution/config
compatibility tests pass (44 tests, same existing warning).
Generation-writer persistence plus status tests pass (28 tests, same existing
warning).

## 4. Failure distribution

No live lesson runs have been recorded in this continuation. Runtime categories now include timeout, validation, provider, persistence, network, and unknown. Lane failure-kind counts are now persisted in the trace execution summary; production distribution is pending attributable runs.

## 5. Latency

No comparable live before/after measurements yet. The configured constrained-node reasoning path is now off by default, and the premium/standard/fast output ceilings are 24k/16k/8k.

## 6. Resume proof

Code-level proof added for prose/questions checkpoint hydration and independent stage completion. Live mid-run kill/reclaim proof remains pending.

## 7. PDF status

PDF export tests pass: 24 tests covering service, telemetry, components, native exports, and health routes. Direct local Playwright launch succeeds after browser installation. The native local render default is now `http://127.0.0.1:5173`. Authenticated browser export for both presets is not yet proven.

## 8. UI changes

No new UI code in this slice. Existing Studio recovery tests pass: 36 focused tests covering chunked status/resume, recovery actions, and failed-section rendering.

## 9. Still broken / unverified

1. Authenticated browser access is unavailable in the current session, blocking real lesson creation and PDF inspection.
2. The long-running backend health endpoint still reports Playwright degraded even though the same virtualenv passes the health check directly; process/runtime provenance needs investigation.
3. Four-lesson acceptance evidence, provider telemetry, live resume kill tests, and worker reclaim evidence remain outstanding. The new completion gate is verified by unit/integration tests only until an authenticated run exercises it live.

## 10. Decisions needed

None requested yet. If authentication remains unavailable, the matrix must remain explicitly incomplete rather than being inferred from unit tests.

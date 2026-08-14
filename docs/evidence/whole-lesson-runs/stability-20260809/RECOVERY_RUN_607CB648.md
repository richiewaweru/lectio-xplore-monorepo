# Corrected-attribution diagnostic successor

Date: 2026-08-09

Generation: `607cb648-213c-4be3-b01e-95d7f73b607a`

This native generation superseded `5c254377-4d7f-40bd-a599-d9a9dd3e0bab` through the visible
Units `Start fresh` workflow. It proved the corrected LLM attempt/retryable fields and native report
projection, then exposed a teaching-exhaustion classification bug. It is not a successful targeted
or final-matrix run.

## Native lineage

- Supersedes: `5c254377-4d7f-40bd-a599-d9a9dd3e0bab`
- Predecessor invalidated: `19:38:00.094772` UTC
- Mode/contract: `v3` / `2`
- Native flags: `true` at both authoritative locations
- Template: guided native path
- Builder record/route: none

## Live item attempt telemetry

| Call | Ledger attempt | Outcome | Retryable | Latency | Error |
| --- | ---: | --- | --- | ---: | --- |
| Item 1 | 1 | failed | true | 120,045.73 ms | `[TimeoutError]` |
| Item 2 | 2 | success | n/a | 89,380.11 ms | none |

The native item-attempt ledger agrees: attempt 1 is `TIMEOUT`/retryable and attempt 2 is `OK`.
Five unique non-stale approved items persisted, with no failed card and no duplicate. Audit-only
ordered item-set MD5: `009ca21289a6e9d5820b8efdc3983eb8`.

This is the first live proof that `llm_calls.attempt` follows the outer item loop and that the final
local attempt can remain inherently retryable even when no local budget remains.

Minor residual: the item-attempt `validation_errors` array contains an empty string for the timeout,
although `llm_calls.error` correctly preserves `[TimeoutError]`.

## Teaching exhaustion

The teaching planner made exactly two calls. Their `llm_calls.attempt` values are correctly 1 and
2. Both provider responses failed structured-output handling with
`[UnexpectedModelBehavior] Exceeded maximum output retries (0)` at 100,463.67 ms and 89,857.09 ms.

The teaching boundary then wrapped the failure as generic `RuntimeError` / `UNKNOWN`, producing
`failed_terminal`. No raw output, validation object, or QC issue was persisted, so the malformed
output is not inspectable beyond the provider exception.

Architecture review classified this as an implementation bug: recognized exhausted model-output
or semantic-plan noncompliance can plausibly change on a checkpoint retry and must become a narrow
typed `MODEL_OUTPUT_INVALID` recoverable teaching failure. Generic programming failures and corrupt
persisted input remain terminal. The persisted terminal row is not reclassified or requeued.

## Report projection proof

- Generation/chunked stage: `failed_terminal`
- Native action: `inspect_error`
- `report_json.native_stage`: `failed_terminal`
- `report_json.process_status`: `failed_terminal`

This proves the new atomic native report projection fixes the prior stale `running` status.
`booklet_status=streaming_preview` is intentionally separate artifact-readiness state and remains
unchanged.

## Downstream cleanliness

- Five approved items exist in the lesson packet.
- No teaching plan/raw/validation/summary exists.
- No form plan/raw/validation exists.
- Zero block outcomes, generation steps, and writer calls.
- No document, revision, or teaching/form/final reload hash exists.

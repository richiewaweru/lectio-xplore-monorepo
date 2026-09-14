# Strict acceptance matrix

Task numbers map to the user-approved list 1–12. Task 0 is the additional login-first prerequisite.

| Gate | Task | Area | Required outcome | Evidence |
|---|---|---|---|---|
| G01 | 0 | Early login | Authenticated implementing browser and verified target/served revision; session reference without secrets. | Browser evidence; unavailable session = BLOCKED. |
| G02 | 0 | Baseline inventory | Pin source SHA, inspect caller graph and record baseline full checks/live attempt. | Raw logs, exact commands and categorized failures. |
| G03 | 1 | Backend health | Full declared backend validator exits zero. | Complete current log; no exclusions to hide failures. |
| G04 | 2 | Current tests | Retired assertions replaced; active invariants tested; architecture guards green. | Old-to-new coverage mapping plus tests. |
| G05 | 3 | Stage registration | All active generation stages mapped; unknown IDs/transitions rejected; approval waits supported. | Registry tests + active-entrypoint coverage map. |
| G06 | 3 | Revision and migration | Existing documents load; unapproved/stale inputs blocked; sibling handoff immutable. | Migration rehearsal, rollback behavior and revision tests. |
| G07 | 5 | Admission idempotency | Concurrent identical requests create one run; changed payload same key conflicts; explicit regeneration new run. | DB-backed concurrency assertions and row counts. |
| G08 | 5 | Effect idempotency | Save/publish/export retries return committed outcome; different stale edits 409; owner scoping enforced. | DB uniqueness and API tests. |
| G09 | 4 | Checkpoint reuse | Saved composition/node IDs/results survive worker death and are not rewritten. | Failure injection + before/after hashes + provider call counters. |
| G10 | 4 | Selective recovery | Failed node/interaction/media/assembly/export reruns only necessary dependency work. | Stage/item invocation counts; successful sibling unchanged. |
| G11 | 6 | Retry budget | Initial + two additional calls maximum under nested transport/schema/quality repairs and fallback. | Fake provider counts across restarts and manual resume. |
| G12 | 6 | Error policy | Retryable provider errors distinguished from permanent errors; Retry-After and deadline honored. | Provider-adapter tests including streaming failure after HTTP 200. |
| G13 | 7 | Lease and cancellation | Expired workers cannot commit; cancel prevents new dispatch/late publish. | Competing-worker tests with fenced writes. |
| G14 | 7 | Bounded resources | Concurrency/deadline/cost limits persisted and enforced; unknown usage explicit. | Concurrent budget reservation tests and exhausted-state proof. |
| G15 | 4,6 | Compatibility and fallback | Incompatible checkpoint resume fails safely; fallback declared, visible and budgeted. | Version-change tests and composition-mode trace assertion. |
| G16 | 8 | Durable status/events | Status agrees with DB; event replay survives disconnect and duplicate delivery. | API replay/retention tests with event sequence. |
| G17 | 8 | Trace and usage | Every actual model call linked to run/path/stage/item/attempt/model/prompt hash. | Sanitized trace sample and accounting assertions. |
| G18 | 8 | Telemetry boundaries | Unauthorized status/events rejected; secrets absent; exporter outage cannot break work. | Authorization/redaction/outage tests. |
| G19 | 9 | Frontend ownership | Thin route controllers; domain stores isolated; shared UI/transport allowed. | Dependency guard + affected component and app checks. |
| G20 | 10 | Navigation recovery | No duplicate subscriptions, stale events or shared busy-state corruption across jobs. | UI tests and browser reconnect proof. |
| G21 | 10 | Edit protection | Progress refresh preserves dirty content; 409 preserves local edits and offers reload/resolve. | Two-editor/browser test; independent sibling hashes. |
| G22 | 11 | Live journey | Fresh Unit to Learn response persistence and native Print edit to actual retained PDF. | One linked run manifest, browser screenshots and PDF binary/text/hash. |
| G23 | 11 | Live recovery | Controlled interruption/reconnect/repeated request preserves outputs and bounded attempts. | Isolated live recovery proof; mock-only is insufficient. |
| G24 | 12 | Finality | All mandatory commands pass on tested implementation; independent verdict and every artifact retained. | Final report, gate matrix, checksums, exact SHAs; no unproved PASS. |

## Final decision
READY only when G01–G24 are PASS for the final implementation and live target. Baseline may be red at P00; G03 must become green at P01. External inability to log in/provider unavailable is BLOCKED, never waived. Missing proofs or unresolved backend failures mean NOT READY. An agent may continue independent work during an external block, but cannot claim dependent live gates.

Do not confuse named state fields with behavior: tests must assert database effects and provider call counts. Different LLM wording is acceptable; semantic coverage, canonical actions, structure, provenance, independence and validation must meet the frozen contracts.

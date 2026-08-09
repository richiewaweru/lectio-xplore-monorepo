# Failure Injection Matrix

| ID | Failure | Injection point | Expected result |
|---|---|---|---|
| F01 | Form transport error | first form call | backoff/retry; no teaching rerun |
| F02 | Form validation error | malformed response | one repair |
| F03 | Writer transport error | middle block | siblings continue; retry failed only |
| F04 | Writer terminal schema error | after repair | no assembly; structured terminal failure |
| F05 | Process killed | writer batch | stale lease reclaimed |
| F06 | Process killed | after blocks, before assembly | DB-first assembly after restart |
| F07 | Duplicate approval | same revision | one execution |
| F08 | Two workers claim | queued job | one owner |
| F09 | Required figure pending | after assembly | awaiting_visuals; PDF conflict |
| F10 | Repeated visual callback | same request | idempotent |
| F11 | Missing block result | assembly | reject exact key |
| F12 | Object/intent mismatch | assembly | reject exact key |
| F13 | Student answer leakage | PDF projection | phase fails |
| F14 | Legacy fallback | new run | phase fails immediately |

Mandatory live subset: F03, F05 or F06, F07, F08, F09, F13, F14.

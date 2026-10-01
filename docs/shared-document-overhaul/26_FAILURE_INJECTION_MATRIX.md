# Failure Injection Matrix

| Scenario | Expected result |
|---|---|
| duplicate admission, same payload | reuse same run |
| same request key, different hash | conflict |
| worker dies after claim | lease expires and another worker recovers |
| stale worker returns late | fence rejects commit |
| provider 429/5xx | bounded transport retry |
| malformed structured output | bounded authoring repair |
| section exhausts repair | failed_recoverable; siblings remain ready |
| targeted section retry succeeds | continue without regenerating siblings |
| checkpoint hash changed | refuse reuse |
| Teaching Plan hash mismatch | block SharedDocument |
| SharedDocument hash mismatch | block Learn/Print |
| required figure fails | SharedDocument not ready |
| continuity issue | targeted affected-section repair |
| repair still fails | recoverable failure, no loop |
| Learn fails | Shared/Print unchanged |
| Print fails | Shared/Learn unchanged |
| backend restart | durable recovery/reconciliation |
| frontend refresh | same authoritative run state |
| cancellation | stale worker cannot later commit |
| programming/auth/config error | no semantic fallback |

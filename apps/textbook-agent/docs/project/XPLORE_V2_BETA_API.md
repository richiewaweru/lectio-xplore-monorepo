# Xplore V2 Beta API

Version: `1.0.0-beta.1`

All endpoints require the existing bearer-token authentication. V2 endpoints additionally require
the authenticated account to pass the server-side Xplore V2 capability check. Ownership failures
and unavailable V2 capability both use non-disclosing `404` responses.

## Capability and compatibility

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/capabilities` | Returns `{ "xplore_v2": boolean }` for the current account. |
| `GET` | `/api/v1/legacy-units` | Returns owned non-V2 packs as computed one-lesson units. |
| `GET` | `/api/v1/legacy-units/{pack_id}` | Returns one owned computed wrapper. |

Compatibility responses are read-only projections. `computed=true` and
`migration_required=false` are explicit guarantees; the endpoints create no units, paths, lessons,
or generations.

## Unit workflow

The `/api/v1/units` family owns unit scope, versioned path planning and approval, lesson structure,
teaching schedules, groups, preparation/regeneration, deterministic composition, actuals, and
aggregate marks. Mutations preserve revision guards and objective hashes. Expensive actions are
rate limited:

| Action | Limit |
| --- | --- |
| Plan/replan path | 6 per minute |
| Prepare lesson | 12 per minute |
| Regenerate lesson | 6 per minute |
| Preview composition | 60 per minute |
| Persist composition | 30 per minute |

Rate-limit responses use `429`. Validation, stale-revision, and approval guards retain their
existing `4xx` contracts. Every `/api/v1/units` mutation records method, path, status, actor when
authenticated, request ID, query metadata, and timestamp in `v2_audit_events`.

## Rollout configuration

- `XPLORE_V2_ENABLED=true|false`: global kill switch; defaults to `true`.
- `XPLORE_V2_BETA_USERS=`: optional comma-separated user IDs or emails. Empty means every
  authenticated account is eligible while the global switch is enabled.

The client always reads `/api/v1/capabilities`; it does not decide eligibility locally.

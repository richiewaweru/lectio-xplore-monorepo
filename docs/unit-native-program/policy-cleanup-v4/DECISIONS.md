# Policy cleanup v4 — DECISIONS

| ID | Decision | Rationale |
| --- | --- | --- |
| D-PC-01 | Policy lives on package writer records (`knowledge`, `assessment`), not native_policy bodies | Packages own capability semantics; native policy only narrows offer lists |
| D-PC-02 | Shared resolver at work-order boundary (`infra.authoring.policy_resolver`) | One semantics for Print + Learn; shared preparation stays path-agnostic |
| D-PC-03 | Default knowledge for eligible generate: `supplied_preferred` | Product decision; explicit source-only tasks stay `supplied_only` |
| D-PC-04 | Default ShortResponse assessment: `automatic_preferred` with teacher-review permitted | Only where runtime supports teacher-review; other interactions stay `automatic_required` |
| D-PC-05 | Explicit task request wins over package default; cannot enable unsupported capability | Precedence; unsupported → `POLICY_CONFLICT` |
| D-PC-06 | Persist resolved decision on provenance / interaction provenance | Editing package defaults must not reinterpret published lessons |
| D-PC-07 | Legacy absent-policy → `legacy-absent-v1` (facts absent; ShortResponse automatic-preferred where supported) | Deterministic; never invent approval claims |
| D-PC-08 | Input availability: `supplied_statements` \| `intentionally_absent` \| `unresolved_references` \| `retrieval_failure` \| `legacy_unknown` | Separate requested policy from actual input |
| D-PC-09 | Facts are statements from preparation snapshot; never id/title/objective/arc | Fixes objective-as-fact defect |
| D-PC-10 | Unresolved refs / load failures fail even under permissive knowledge policy | Fallback must not conceal broken dependencies |
| D-PC-11 | Missing answers under `automatic_required` → typed failure (convert never invents answers) | Supersedes silent teacher-review inference |
| D-PC-12 | Builder PUT runs `validate_interaction_contract` | G21 requires rejection on edit route, not only publish |
| D-PC-13 | Failure code `POLICY_CONFLICT`; not retryable | Distinct from missing input / incompatible approved item |
| D-PC-14 | Print gets knowledge policy only; Learn evaluation does not enter Print layout | Preserve Print teacher/student variants |

## Typed error mapping

| Condition | Code |
| --- | --- |
| Unsupported / contradictory policy | `POLICY_CONFLICT` |
| Blank required objective / insufficient capability inputs | `MISSING_AUTHORING_INPUT` |
| Unresolved fact refs (when references present) | `MISSING_AUTHORING_INPUT` |
| Missing approved item / incompatible convert | `INCOMPATIBLE_APPROVED_ITEM` |
| Automatic-required convert without answers | `INCOMPATIBLE_APPROVED_ITEM` |
| Model attempts to alter trusted policy | stripped / ignored (existing R01-G03) |

## Migration

- New authored material: package defaults + resolver decision snapshot.
- Published releases: immutable snapshots already carry contract config; defaults do not rewrite them.
- Legacy drafts without snapshot: `legacy-absent-v1` reader only.

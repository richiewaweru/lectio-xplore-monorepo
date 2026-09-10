# Policy cleanup v4 — PLAN

## Baseline

| Field | Value |
| --- | --- |
| Branch | `feat/unit-print-learn` |
| HEAD at P0 | `c3563abbb141443bc0131917d09de81a8e4c118a` |
| Reviewed baseline | `c3563abbb141443bc0131917d09de81a8e4c118a` (exact match) |
| Remaining-fixes verified | `4b6bbc4694bb996e857f500772f6fe773531d63f` |
| Commits since remaining-fixes | docs R05/v2 correction; DeepSeek flash slot switch |
| Working tree | Unrelated dirty: `.tmp/`, backend logs/data, P09 scripts, p05 page-image artifacts — **preserved, not committed** |

## Ownership map

| Concern | Owner | Key symbols |
| --- | --- | --- |
| Capability defaults / supported modes | Package writer views | `LearnWriterRecord`, `FormWriterRecord` |
| Shared policy resolution | Shared authoring | `infra.authoring.policy_resolver` |
| Knowledge context extraction | Learn prep | `learn_preparation_context_from_state` |
| Work-order authoring | Native adapters | `run_learn_authoring`, `run_print_authoring` |
| Assessment conversion | Learn adapter | `_convert_short_response` |
| Runtime evaluation | Learn runtime | `evaluate_short_response`, `submit_attempt` |
| Persist / publish | Learn publishing + dual native | `produce_learn_from_approved_teaching`, `publish_learn_release` |

## Defects to fix

1. Objective/title/arc → `allowed_facts` substitution in `preparation_context.py`.
2. Brief / `"Offline fixture fact."` invention in `interaction_writer.py`.
3. Global nonempty-facts rejection for generate (`_validate_teaching_context`) — supersedes remaining-fixes blanket ban.
4. Missing ShortResponse answers → silent `teacher-review` in `_convert_short_response`.
5. Print executor does not thread packet statements into `allowed_facts`.
6. Builder PUT is structural-only; incompatible assessment edits must fail on save.

## Phase plan

| Phase | Gates | Intent |
| --- | --- | --- |
| P0 | G01 | Baseline map (this document) |
| P1 | G02–G05 | Package policy + shared resolver + provenance snapshot |
| P2 | G06–G12 | Honest knowledge context (Learn + Print) |
| P3 | G13–G18 | Explicit assessment conversion / runtime / Builder |
| P4 | G19–G24 | Verification, regression sensitivity, retained gates |

## Superseded vs retained gates

### Superseded (equivalent coverage required)

| Prior | Replacement |
| --- | --- |
| `test_r02_g05_empty_facts_fail_for_generate` | G06 + G07 + G10 |
| R01/A04 convert-without-answer → automatic teacher-review | G14 + G15 + G16 |

### Retained unchanged

R00–R05 (except superseded clauses), v2 A02/A04/A05/A06, P06/P07/P08, R01-G03 trusted fields, R02 source resolver, R04 persist/publish/attempts.

## Caller map

See [tracking/CALLER_MAP.md](tracking/CALLER_MAP.md).

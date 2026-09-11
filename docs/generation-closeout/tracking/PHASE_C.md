# Phase C — Twin Learn/Print realization

Status: PASS

## CURRENT
Maps were Python dicts; twin fidelity not proven on closeout path.

## CHANGE
Learn/Print maps load from `resources/policies/*.yaml`. Same plan realizes Learn `choice` and Print `choices` for `select-one`. Documented `source_question_ids` ownership exception retained.

## CANONICAL CALLER
`learn.generation.document_realizer` / `print.generation.document_realizer` → YAML action maps via `core.policies.loader`

## TEST
`uv run pytest tests/core/policies/test_action_maps.py tests/print_learn/test_document_realizers.py -q`

## LIVE PROOF
Shared conceptual plan twin in `phase-b-c-d-live.json`: `select_one_ok=true`; no-action explain blocks stay document-only on both paths.

## STATUS
PASS

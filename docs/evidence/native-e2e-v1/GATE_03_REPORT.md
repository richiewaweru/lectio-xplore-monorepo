# Gate 3 — Questions, choices, and answer key

## Pass

Assessment path separates student blocks from answer entries; document assembly merges a top-level `answer_key`.

## Summary

- `questions` content has no MCQ metadata (`correct_key` / options forbidden).
- `choices` is a first-class form with stem + lettered options.
- `AssessmentBundle` + `AnswerEntry` models; `validate_answer_key_integrity` enforces exact ID match, no orphans/duplicates, MCQ letter membership.
- `assemble_document_v2(..., answer_entries=...)` builds `answer-key` block.

## Tests

- `tests/generation/test_assessment_bundle.py`
- `tests/generation/test_answer_key_integrity.py` (package coverage)

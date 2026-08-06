# Gate 7 — Assembly answer merge

## Pass

`assemble_from_db` merges block `answer_entries` into `assemble_document_v2` and uses section titles when available.

## Changes

- Optional `FormPlanSection.title` field.
- Title resolution: form title → teaching `specific_purpose` → slot_id title-case.
- Collect `answer_entries` from all ready block outcomes; pass into `assemble_document_v2`.
- `_writer_result_from_outcome` restores `answer_entries` for integrity validation.

## Verification

Covered by phase02 assembly round-trip tests plus assessment/answer-key generation tests in the targeted suite.

# Scripted Mock Provider Specification

## Purpose

The mock provider must prove application behavior independently of provider quality.

It should implement the same interface consumed by the general writer engine. It must support deterministic responses by:

- section ID;
- block ID;
- requested object;
- attempt number;
- named scenario.

## Suggested interface

```python
class ScriptedWriterProvider:
    async def write(
        self,
        *,
        object_id: str,
        section_id: str,
        block_id: str,
        attempt: int,
        prompt: str,
        output_model: type[BaseModel],
    ) -> object:
        ...
```

## Requirements

- No network.
- Deterministic output.
- Capture every call.
- Capture prompt hash and relevant payload.
- Enforce maximum expected call count.
- Can delay selected sections to test completion order.
- Can throw transport-like exceptions.
- Can return strings, dictionaries, or typed objects.
- Can inspect repair prompts and assert they contain:
  - previous invalid output;
  - validation errors;
  - requested object;
  - original brief.

## Scenario behaviors

### valid_first_time

Return valid content for every object on attempt 1.

### invalid_json_then_valid

Attempt 1 returns truncated JSON text.  
Attempt 2 returns valid content.

Expected:

- parse failure;
- repair call;
- final ready;
- two recorded calls.

### wrong_schema_then_valid

Example for table:

Attempt 1:

```json
{"paragraphs": ["This is prose, not a table."]}
```

Attempt 2 returns valid table.

Expected: selected table validator rejects attempt 1.

### extra_fields_then_valid

Example for questions:

Attempt 1 includes forbidden `correct_key` inside an item.  
Attempt 2 returns only allowed question fields.

### wrong_object_then_valid

Attempt 1 wraps or labels content as a different object.  
The fixed-object invariant rejects it.

### permanently_invalid

Both attempts fail validation.

Expected:

- structured recoverable block/section failure;
- error contains validation details;
- other sections remain persisted;
- no assembly.

### transport_failure_then_valid

Attempt 1 raises a transport exception.  
Retry returns valid content.

Expected:

- transport retry does not consume schema repair;
- backoff path exercised.

### timeout_exhausted

All transport attempts fail.

Expected: structured recoverable provider failure.

### out_of_order_sections

Delay sections:

```text
section-3: 10 ms
section-1: 20 ms
section-4: 30 ms
section-2: 40 ms
```

Expected final order: 1,2,3,4.

### duplicate_answer_id

Return an assessment bundle with duplicate question IDs.

Expected deterministic integrity failure before persistence.

### orphan_answer

Return answer for unknown question ID.

### missing_answer

Return assessed item without answer entry.

### invalid_mcq_answer

Return answer `D` while choices contain only `A`, `B`, `C`.

### figure_missing_alt

Return pending figure without `alt_text`.

### section_partial_resume

First run completes sections 1 and 2, then fails section 3.  
Second run must skip 1 and 2 and continue 3 and 4.

## Call evidence format

```json
{
  "scenario": "extra_fields_then_valid",
  "section_id": "section-4",
  "block_id": "q-open-1",
  "object": "questions",
  "attempt": 1,
  "result_kind": "dict",
  "validation_passed": false,
  "validation_errors": ["items.0.correct_key: extra field"],
  "repair_prompt_contains_prior_output": true
}
```

# Writer Repair Prompt Template

## System instruction

Correct a previously invalid page-object content response. Do not redesign the block and do not change its object, intent, ID, or educational purpose.

Return the complete corrected JSON content object only.

## Repair payload

```json
{
  "requested_object": "{{ object }}",
  "block_id": "{{ block_id }}",
  "intent": "{{ intent }}",
  "original_brief": "{{ brief }}",
  "writer_contract": {{ schema }},
  "previous_invalid_output": {{ previous_output }},
  "validation_errors": [
    {
      "path": "{{ path }}",
      "message": "{{ message }}"
    }
  ]
}
```

## Mandatory instruction

Fix every listed validation error while preserving correct content from the previous response. Do not add properties outside the schema. Do not include markdown fences or commentary.

## Test assertion

The mock provider test must verify that the repair call contains:

- requested object;
- original brief;
- previous invalid output;
- every exact validation error.

# Resource Projections

## Principle

Canonical lesson material is authored once. Resources are composed from it where possible.

## Projection types

### Full lesson/booklet

- all approved instructional slots;
- shared check;
- optional student/teacher preset.

### Homework

- selected guided/independent/apply blocks;
- shared or alternate approved items;
- no exposition unless teacher requests support notes.

### Revision sheet

- objective;
- key definitions;
- organising structure;
- contrast/pitfall summary;
- selected examples.

### Flashcards

- concept title;
- objective fragments;
- definitions;
- misconception corrections where suitable.

### Quiz

- shared diagnostic items;
- optionally pooled module items.

### Answer key

- correct answers;
- misconception hypotheses;
- teacher notes.

### Unit exam

- pooled items across selected concepts;
- coverage report;
- no model call for selection unless new items are explicitly requested.

## Compose API

```text
POST /api/v1/units/{id}/compose
```

Input:

```json
{
  "projection": "revision",
  "path_lesson_ids": ["..."],
  "group_ids": ["..."],
  "include_keys": false
}
```

## Zero-model-call rule

A projection must not call an LLM when it can be represented through deterministic selection and formatting.

## Provenance

Projection records:

- source pack/version;
- selected components;
- item IDs;
- projection template version.

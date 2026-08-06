# Architecture and Settled Decisions

## Production flow

```text
Request
  ↓
Native lesson preparation and planning
  ↓
Teacher approval
  ↓
Form plan
  ↓
Section execution coordinator
  ├── Section 1
  ├── Section 2
  ├── Section 3
  └── Section 4
  ↓
Validated section outcomes
  ↓
Deterministic document assembly
  ↓
LectioDocumentV2 validation and persistence
  ↓
Student and teacher views/PDFs
```

## Concurrency

- Main unit: section.
- Maximum concurrent sections: 4.
- Completion order must never affect canonical document order.
- Blocks can run concurrently inside a section only when no dependency is declared.
- Assessment questions and answers are generated together.
- A worked example followed by questions that depend on it should be sequential or generated with shared context.

## Writer architecture

One engine, multiple strict output contracts:

```text
GeneralWriter.write(requested_object, context)
  ↓
FORM_OUTPUTS[requested_object]
  ↓
typed validated content
```

Supported generated forms:

- prose
- list
- table
- figure
- aside
- worked-example
- questions
- choices

Structural forms:

- heading: section title in normal Xplore generation
- answer-key: assembled at document level

The explicit Lectio `heading` object remains valid for nested/imported/manual documents and library tests.

## Assessments

```text
AssessmentBundle
├── student_blocks
│   ├── questions
│   └── choices
└── answer_entries
```

Stable identity rules:

- `questions.items[].id` is the answer key `question_id`.
- A `choices` block's `id` is its answer key `question_id`.
- No answer IDs are invented in a second pass.
- Answers are never embedded in student `questions` content.

## Figures

Figure generation is non-blocking in this pass.

- Create stable request ID.
- Save asset status `pending`.
- Require useful `alt_text`.
- Render a visible placeholder.
- Mark the document ready even when figures remain pending.
- A later visual callback may replace the asset without rewriting lesson content.

## Validation

Three levels:

1. form content validation immediately after each writer;
2. cross-reference validation before document assembly;
3. full Lectio document validation before and after persistence.

## Failure policy

| Failure | Behavior |
|---|---|
| malformed JSON | one informed repair, then recoverable writer failure |
| schema-invalid output | one informed repair, then recoverable writer failure |
| transport timeout/rate limit | bounded retry with backoff |
| unsupported object | programming failure; test must catch before runtime |
| answer reference mismatch | deterministic validation failure |
| assembly invariant failure | programming failure with exact diagnostic |
| lost worker lease | stop work; do not overwrite newer worker |
| pending visual | not a document failure |

## State model

Recommended native states:

```text
preparing
planning
awaiting_teacher
planning_forms
writing_sections
assembling
ready
failed_recoverable
failed_terminal
```

`failed_recoverable` requires actionable retry metadata. `failed_terminal` requires a non-null programming/invariant diagnostic.

## Legacy policy

- No new native request may route through legacy code.
- Historical records can be read through a compatibility reader if required.
- Do not use an adapter to convert native v2 into v1.
- Do not preserve two active production pipelines.

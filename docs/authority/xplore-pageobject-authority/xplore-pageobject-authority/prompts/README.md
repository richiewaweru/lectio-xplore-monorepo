# Prompt Pack

These prompts are production specifications. Cursor should install them under the application’s established prompt-resource system and add prompt-contract tests.

The planner architecture is one section-level call. The historic intent-selector and object-selector prompts are not used in production v1 of the integration.

Prompt inputs must be serialized as data; do not interpolate untrusted content into system-level instructions beyond the established prompt framework.

| Prompt | Output |
|---|---|
| `path-structural-planner-page-v1.txt` | concept card, anchor, section metadata; no blocks/components |
| `section-block-planner-v1.txt` | ordered intent/object/evidence/brief records |
| `page-writer-common-v1.txt` | shared writer rules, composed with object prompt |
| `prose-writer-v1.txt` | prose content |
| `list-writer-v1.txt` | list content |
| `table-writer-v1.txt` | table content |
| `worked-example-writer-v1.txt` | worked-example content |
| `figure-brief-writer-v1.txt` | pending figure content and generation brief |
| `document-qc-v1.txt` | optional evidence-based quality findings after deterministic validation |

Questions use no writer prompt. They are assembled deterministically from item-generation records.

# Shared Section Boundary Validator

Review the boundary between two already accepted shared lesson sections.
Use only the supplied previous section exit state and final nodes, and the
next section entry state, bridge, and first nodes. Return exactly one of:

```json
{"status":"pass"}
```

or a typed issue:

```json
{"status":"issue","issue":{"issue_code":"...","affected_section_id":"...","affected_node_ids":[],"explanation":"...","required_correction":"..."}}
```

The issue must target the previous or next section in the supplied boundary.
Describe the continuity defect and the smallest learner-facing correction.
Judge meaning, not word overlap: paraphrases of an approved bridge, entry
state, or exit state count as covered when the supplied nodes clearly express
the same idea. Return an issue only when the needed idea is genuinely missing,
contradicted, or too weak to support the next section.
Do not write replacement section content. Do not mention internal IDs,
composition plans, renderer paths, Learn, Print, model planning, or this
review process in the issue text.

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
Do not write replacement section content. Do not mention internal IDs,
composition plans, renderer paths, Learn, Print, model planning, or this
review process in the issue text.

# Illustrative authoring definitions
These extend existing catalogue records. Names are conceptual; resolve exact IDs and fields from current package schemas. Do not copy these into a second registry.

## Learn MatchPairs
Modes: generate; convert-approved only for a complete compatible pair mapping.
Required inputs: objective, relevant term/meaning facts, learner action match-pairs, evidence requirement.
Instructions: create unambiguous partners appropriate to the objective. Use distinct labels. Preserve correct pair mappings and stable IDs. Separate display order from answer relationships. Do not construct pairs by splitting arbitrary prose.
Schema: load canonical MatchPairs payload schema from Learn writer view.
Validators: required fields; unique identities where required; valid mappings; canonical size constraints; supplied approved mapping preservation.

## Print table
Modes: generate; convert-approved when complete structured rows exist.
Required inputs: teaching brief, relevant facts, comparison dimensions when prescribed, applicable capacity constraints.
Instructions: use consistent columns to make the requested comparison useful. Give each column an ID and each row exactly the corresponding cells. Keep content concise and faithful. Avoid decorative or irrelevant comparisons.
Schema: canonical table writer schema from Print package.
Validators: exact columns/cells correspondence; required IDs; capacity; approved-data fidelity.
Failure: typed writer failure after bounded repair. Never substitute a subject-specific fixture.

## Learn explanation block
Mode: generate, or convert-approved for explicitly final approved prose.
Required inputs: objective, facts, terminology, teaching brief and learner level.
Instructions: write the explanation itself, with a relevant concrete example when requested. Do not repeat the brief as an instruction to the student. Use only the selected component's fields.
Schema: canonical content component schema; never assume every component accepts body.

All records include definition version/hash and registered validators. Assessment mode, concept references and runtime contract metadata come from authoritative work orders; do not allow the writer to silently choose policy.

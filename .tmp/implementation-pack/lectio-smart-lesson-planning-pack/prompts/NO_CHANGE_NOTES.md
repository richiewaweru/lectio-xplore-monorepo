# Prompts that should probably remain unchanged

## `document-composer.md`

Current behavior is already aligned with the target architecture:

- receives approved Teaching Plan;
- chooses ordinary primitive structure only;
- stays inside closed per-block allowlists;
- does not author learner interactions.

The composer may need additional input metadata such as Sourcebook binding availability, but its core prompt does not need to become a lesson planner.

## `interaction-selection.md`

Current behavior is also aligned:

- receives one path-agnostic learner action;
- chooses from an exact retained Learn shortlist;
- preserves task meaning;
- prefers the simplest faithful representation.

Keep that separation. The important change is that the interaction writer consumes a SharedTaskSpec rather than inventing task content after selection.

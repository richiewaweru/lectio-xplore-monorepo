# Concept Registry

## Purpose

The registry creates a stable identity layer across:

- paths;
- cards;
- generated lessons;
- diagnostics;
- booklets;
- future responses.

## Canonical versus contextual fields

Canonical:

- concept ID;
- canonical slug;
- subject;
- general title.

Contextual:

- grade-specific objective;
- prerequisites in this path;
- exclusions;
- terminology;
- misconceptions;
- lesson skeleton.

Do not place every grade-specific statement on the canonical concept row.

## Resolution flow

When a path planner proposes a lesson:

```text
proposed concept
  ↓
search registry by subject + semantic title
  ↓
candidate match
  ├── teacher confirms existing concept
  └── create new concept
```

For MVP, matching can be exact/normalized plus optional semantic suggestions. Never silently merge concepts.

## API

```text
GET  /api/v1/concepts?q=&subject=
POST /api/v1/concepts
GET  /api/v1/concepts/{id}
PATCH /api/v1/concepts/{id}
POST /api/v1/concepts/{id}:deprecate
```

## Invariants

- canonical slug unique;
- deprecated concepts remain referentially valid;
- merges require explicit migration;
- a path replan attempts to retain concept IDs;
- generated provenance always stores concept ID and objective hash.

## Tests

- replan preserves IDs for unchanged concepts;
- renamed lesson retains concept ID;
- split creates explicit new concept candidates;
- merge never silently discards source identities;
- deprecated concepts remain readable.

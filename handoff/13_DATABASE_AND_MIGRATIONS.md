# Database and Migrations

## New tables

```text
concepts
units
unit_scope_contracts
path_versions
path_lessons
path_lesson_prerequisites
teaching_periods
teaching_period_lessons
unit_groups
lesson_provenance
lesson_actuals
skeleton_shadow_records
resource_compositions
marks_entries
```

## Existing tables referenced

- generation rows;
- pack/card/item tables;
- documents;
- Builder lessons;
- users.

## Additive migrations first

### Migration 1

- concepts;
- nullable canonical concept ID on current card persistence;
- provenance fields/table;
- objective hash.

### Migration 2

- skeleton shadow records;
- no behavior change.

### Migration 3

- units/path versions/path lessons;
- optional pack link.

### Migration 4

- teaching periods/groups.

### Migration 5

- compositions/actuals/marks.

## No destructive migration

Existing packs are not rewritten.

Legacy pack wrapper is computed or stored additively.

## Constraints

- canonical slug unique;
- path version + position unique;
- one active pack per path-lesson revision;
- check item ownership remains pack-level;
- marks item IDs resolve to pack-owned items;
- provenance immutable after publication except append-only deviation status.

## Upgrade tests

Every migration:

- upgrade;
- downgrade where supported;
- upgrade again;
- existing fixture data remains readable.

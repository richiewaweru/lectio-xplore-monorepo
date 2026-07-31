# API Contracts

## Concepts

```text
GET  /api/v1/concepts?q=&subject=
POST /api/v1/concepts
GET  /api/v1/concepts/{id}
PATCH /api/v1/concepts/{id}
```

## Skeletons

```text
POST /api/v1/skeletons:preview
GET  /api/v1/skeletons
GET  /api/v1/skeletons/{id}
GET  /api/v1/skeletons/shadow-report
```

Preview request:

```json
{
  "objective": "Explain how light causes water splitting.",
  "lesson_mode": "first_exposure",
  "misconception_count": 1,
  "group_profiles": ["support", "core", "extension"]
}
```

## Units and paths

```text
POST /api/v1/units
GET  /api/v1/units
GET  /api/v1/units/{id}
PATCH /api/v1/units/{id}

POST /api/v1/units/{id}/path:plan
POST /api/v1/units/{id}/path:replan
POST /api/v1/units/{id}/path:approve

PATCH /api/v1/units/{id}/path/lessons/{lesson_id}
POST  /api/v1/units/{id}/path/lessons/{lesson_id}:skip
POST  /api/v1/units/{id}/path/lessons/{lesson_id}:split
POST  /api/v1/units/{id}/path/lessons:merge
```

## Scheduling

```text
GET  /api/v1/units/{id}/schedule
PUT  /api/v1/units/{id}/schedule
POST /api/v1/units/{id}/schedule:suggest
```

Schedule suggestion may use time, but may not mutate the path.

## Lesson preparation

```text
POST /api/v1/units/{id}/path/lessons/{lesson_id}:prepare
GET  /api/v1/units/{id}/path/lessons/{lesson_id}/status
POST /api/v1/units/{id}/path/lessons/{lesson_id}:record-actual
```

## Compose

```text
POST /api/v1/units/{id}/compose:preview
POST /api/v1/units/{id}/compose
GET  /api/v1/units/{id}/compositions/{composition_id}
```

## Marks

```text
POST /api/v1/units/{id}/path/lessons/{lesson_id}/marks
GET  /api/v1/units/{id}/path/lessons/{lesson_id}/marks-summary
```

## Legacy

Retain:

- `/studio`;
- `/packs/*`;
- `/builder/*`;
- current print and generation routes.

## Error policy

Never return a plausible partial path as complete.

Use explicit states:

- `needs_scope_review`;
- `prerequisite_gap`;
- `skeleton_conflict`;
- `variant_slot_overflow`;
- `legacy_adapter_required`;
- `projection_unavailable`.

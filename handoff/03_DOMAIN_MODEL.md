# Domain Model

## Concept

```python
Concept:
    id: UUID
    canonical_slug: str
    subject: str
    title: str
    canonical_description: str | None
    status: draft | active | deprecated
    created_by: UUID
    created_at
    updated_at
```

Concept identity is stable. Objectives are contextual and live on PathLesson.

## Unit

```python
Unit:
    id
    owner_id
    title
    topic
    subject
    grade_level
    curriculum_context
    status
    active_path_version
```

## UnitScopeContract

```python
UnitScopeContract:
    unit_id
    must_establish[]
    may_include[]
    must_not_introduce[]
    assumed_prerequisites[]
    terminology[]
    notation
    final_evidence[]
```

## PathVersion

```python
PathVersion:
    id
    unit_id
    version
    status: draft | review | approved | superseded
    generated_by
    approved_at
```

## PathLesson

```python
PathLesson:
    id
    path_version_id
    concept_id
    title
    objective
    prerequisites[]          # concept IDs where resolvable
    external_prerequisites[]
    opens_from
    must_establish[]
    exclusions[]
    primary_knowledge_type
    secondary_demand
    knowledge_type_source
    merge_warning
    position
    source
    teacher_edited
    skipped
    pack_id | null
```

## TeachingPeriod

```python
TeachingPeriod:
    id
    path_version_id
    title
    position
    concept_lesson_ids[]
    planned_minutes | null
    teacher_note | null
```

Periods do not own concepts or generated packs. They group path lessons for scheduling.

## UnitGroup

```python
UnitGroup:
    id
    unit_id
    label
    description
    toggle_profile
    voice
    position
```

## LessonProvenance

```python
LessonProvenance:
    pack_id
    concept_id
    path_version_id
    path_lesson_id
    objective_hash
    skeleton_id
    skeleton_version
    knowledge_type
    knowledge_type_source
    secondary_demand
    toggles_applied[]
    deviations_requested[]
    deviations_approved[]
    component_registry_version
    planner_prompt_version
```

## LessonActual

```python
LessonActual:
    path_lesson_id
    status: established | partial | recovery_needed | not_taught
    established_concepts[]
    unresolved_misconceptions[]
    anchor_used | null
    teacher_note | null
    recorded_at
```

## MarksEntry

```python
MarksEntry:
    unit_id
    path_lesson_id
    pack_id
    group_id
    item_id
    option_id
    count
```

No learner account is required in Product A.

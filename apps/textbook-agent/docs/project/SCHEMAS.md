# Schemas

Current live schema sources are:

- `backend/src/core/database/models.py`
- `backend/src/core/entities/`
- `backend/src/planning/models.py`
- `backend/src/pipeline/api.py`
- `backend/src/pipeline/types/`
- `backend/src/generation/dtos/`
- `frontend/src/lib/types/`

## Core Stored Entities

### `Generation`

- `id`
- `user_id`
- `subject`
- `context`
- `mode`
- `status`
- `document_path`
- `error`, `error_type`, `error_code`
- `requested_template_id`, `resolved_template_id`
- `requested_preset_id`, `resolved_preset_id`
- `section_count`
- `quality_passed`
- `generation_time_seconds`
- `planning_spec_json`
- `created_at`, `completed_at`

### `StudentProfile`

Persistent teacher/learner-profile data used to derive runtime defaults such as grade band and audience fit.

### `User`

Authenticated shell identity.

## Live Planning DTOs

### `TeacherBrief`

Teacher Studio now plans from a structured brief:

- `subject`
- `topic`
- `subtopics[]`
- `grade_level`
- `grade_band`
- `class_profile`
- `learner_context`
- `intended_outcome`
- `resource_type`
- `supports[]`
- `depth`
- optional `teacher_notes`

### `BriefValidationRequest`

- `brief: TeacherBrief`

### `BriefValidationResult`

- `is_ready`
- `blockers[]`
- `warnings[]`
- `suggestions[]`

### `BriefReviewRequest`

- `brief: TeacherBrief`

### `BriefReviewResult`

- `coherent`
- `warnings[]`
- `feasibility`

`feasibility` currently includes:

- `subtopics_fit`
- `depth_adequate`
- `supports_compatible`

Each review warning includes:

- `message`
- optional `suggestion`
- `severity: "warning" | "info"`

### `PlanningGenerationSpec`

- `id`
- `template_id`
- `preset_id`
- `mode`
- `template_decision`
- `lesson_rationale`
- `directives`
- `committed_budgets`
- `sections[]`
- optional `warning`
- `source_brief_id`
- `source_brief: TeacherBrief`
- `status: draft | reviewed | committed`

Each planning section can include:

- `title`
- `objective`
- `focus_note`
- `selected_components[]`
- `bridges_from`, `bridges_to`
- `terms_to_define[]`
- `terms_assumed[]`
- `practice_target`
- `visual_policy`
- `visual_placements[]`

### `GenerationAcceptedResponse`

- `generation_id`
- `status`
- `events_url`
- `document_url`
- `report_url`
- `section_count`
- `sections_with_visuals`
- `subtopics_covered[]`
- optional `warning`

### `PlanningTemplateContract`

Served by `GET /api/v1/contracts` and derived from the synced Lectio contract catalog. App-facing typed payloads include fields such as:

- `id`, `name`, `family`, `intent`, `tagline`
- `required_components[]`, `optional_components[]`
- `always_present[]`, `available_components[]`
- `component_budget`
- `max_per_section`
- `section_role_defaults`
- `allowed_presets[]`

`signal_affinity` is not part of the live typed contract response.

## Generation Artifact

### `PipelineDocument`

- `generation_id`
- `subject`
- `context`
- `mode`
- `template_id`
- `preset_id`
- `status`
- `section_manifest[]`
- `sections[]`
- `partial_sections[]`
- `failed_sections[]`
- `qc_reports[]`
- optional `error`
- `quality_passed`
- `created_at`, `updated_at`, optional `completed_at`

`SectionContent` remains Lectio-aligned and is sourced from `backend/src/pipeline/types/section_content.py`.

## Live Endpoints

Supported planning endpoints:

- `POST /api/v1/brief/resolve-topic`
- `POST /api/v1/brief/validate`
- `POST /api/v1/brief/review`
- `POST /api/v1/brief/plan`
- `POST /api/v1/brief/commit`
- `GET /api/v1/contracts`

Supported generation/viewer endpoints:

- `GET /api/v1/generations/{id}`
- `GET /api/v1/generations/{id}/document`
- `GET /api/v1/generations/{id}/report`
- `GET /api/v1/generations/{id}/events`
- `POST /api/v1/generations/{id}/export/pdf`

Unsupported legacy endpoints:

- `POST /api/v1/brief`
- `POST /api/v1/brief/stream`
- `POST /api/v1/generations`

## Viewer Contract

- The generation ID is the public viewer identity.
- `/studio` plans through `TeacherBriefBuilder`, reviews a frozen `PlanningGenerationSpec`, then hands off to `GenerationView`.
- Generation hydration comes from `/document` and `/report`; live progress comes from `/events`.
- Raw filesystem paths remain internal implementation details.

# Schemas - v0.1.0

All domain entities are Pydantic v2 models defined in `backend/src/textbook_agent/domain/entities/`. They are the single source of truth for data contracts across the entire pipeline.

## Value Objects

### Depth

Location: `domain/value_objects/depth.py`

| Value | Description |
|---|---|
| `survey` | Core sections only, light coverage |
| `standard` | Core + key supplementary sections |
| `deep` | Full coverage including all supplementary material |

### NotationLanguage

Location: `domain/value_objects/notation_language.py`

| Value | Description |
|---|---|
| `plain` | Plain English, no mathematical symbols |
| `math_notation` | Standard mathematical notation |
| `python` | Python code-style notation |
| `pseudocode` | Pseudocode notation |

### SectionDepth

Location: `domain/value_objects/section_depth.py`

| Value | Description |
|---|---|
| `light` | Brief introduction |
| `medium` | Standard treatment with examples |
| `deep` | Thorough coverage with multiple examples |

---

## Entities

### GenerationContext

Location: `domain/entities/generation_context.py`
Pipeline role: **Input** - ephemeral per-generation context assembled from `StudentProfile` + request. Built fresh for each run, never stored.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `subject` | `str` | required | Subject domain e.g. "calculus", "DSA" |
| `age` | `int` | 8-99 | Drives vocabulary complexity, tone |
| `context` | `str` | required | What the learner knows and struggles with for this topic |
| `depth` | `Depth` | enum | Controls section depth and example count |
| `language` | `NotationLanguage` | enum | Preferred notation style |
| `education_level` | `EducationLevel` | enum | Student's education stage |
| `interests` | `list[str]` | optional | Topics for personalised examples |
| `learning_style` | `LearningStyle` | enum | Preferred learning modality |
| `goals` | `str` | optional | What the learner wants to achieve |
| `prior_knowledge` | `str` | optional | Broad prior knowledge across subjects |
| `learner_description` | `str` | optional | Free-text description of abilities, gaps, and signals |

Example:
```json
{
  "subject": "calculus",
  "age": 17,
  "context": "I understand derivatives but integration confuses me.",
  "depth": "standard",
  "language": "math_notation",
  "education_level": "high_school",
  "interests": ["physics", "gaming"],
  "learning_style": "visual",
  "goals": "Prepare for AP Calculus exam",
  "prior_knowledge": "Comfortable with algebra and trigonometry",
  "learner_description": "Strong at mechanical procedures but struggles with conceptual understanding"
}
```

### SectionSpec

Location: `domain/entities/curriculum_plan.py`
Pipeline role: Describes a single section in the curriculum.

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | required | e.g. "section_03" |
| `title` | `str` | required | Section title |
| `learning_objective` | `str` | required | What the learner will understand |
| `prerequisite_ids` | `list[str]` | `[]` | Section IDs that must come before |
| `needs_diagram` | `bool` | `False` | Whether section needs a visual |
| `needs_code` | `bool` | `False` | Whether section needs a code example |
| `is_core` | `bool` | `True` | False = supplementary, skippable at survey depth |
| `estimated_depth` | `SectionDepth` | required | Light, medium, or deep |

### CurriculumPlan

Location: `domain/entities/curriculum_plan.py`
Pipeline role: **Node 1 output** - full textbook structure.

| Field | Type | Description |
|---|---|---|
| `subject` | `str` | Subject being taught |
| `total_sections` | `int` | Number of sections |
| `sections` | `list[SectionSpec]` | All section specifications |
| `reading_order` | `list[str]` | Ordered list of section IDs |

### SectionContent

Location: `domain/entities/section_content.py`
Pipeline role: **Node 2 output** - generated content for one section.

| Field | Type | Description |
|---|---|---|
| `section_id` | `str` | Links to SectionSpec.id |
| `hook` | `str` | Opening paragraph - felt problem before named solution |
| `plain_explanation` | `str` | Concept in plain language, no jargon |
| `formal_definition` | `str` | Precise definition, notation where appropriate |
| `worked_example` | `str` | Full example, every step explained |
| `common_misconception` | `str` | One thing learners consistently get wrong |
| `connection_forward` | `str` | One sentence linking to next section |

### SectionDiagram

Location: `domain/entities/section_diagram.py`
Pipeline role: **Node 3 output** - SVG diagram for one section.

| Field | Type | Description |
|---|---|---|
| `section_id` | `str` | Links to SectionSpec.id |
| `svg_markup` | `str` | Complete inline SVG (self-contained) |
| `caption` | `str` | One sentence describing the diagram |
| `diagram_type` | `str` | e.g. "number_line", "function_plot", "tree" |

### SectionCode

Location: `domain/entities/section_code.py`
Pipeline role: **Node 4 output** - code example for one section.

| Field | Type | Default | Description |
|---|---|---|---|
| `section_id` | `str` | required | Links to SectionSpec.id |
| `language` | `str` | `"python"` | Programming language |
| `code` | `str` | required | Syntactically valid, runnable code |
| `explanation` | `str` | required | What to observe when running |
| `expected_output` | `str` | required | What the code prints/returns |

### RawTextbook

Location: `domain/entities/textbook.py`
Pipeline role: **Node 5 output** - assembled textbook ready for rendering.

| Field | Type | Default | Description |
|---|---|---|---|
| `subject` | `str` | required | Subject being taught |
| `profile` | `GenerationContext` | required | Per-generation context |
| `plan` | `CurriculumPlan` | required | Curriculum structure |
| `sections` | `list[SectionContent]` | required | All section content |
| `diagrams` | `list[SectionDiagram]` | `[]` | Generated diagrams |
| `code_examples` | `list[SectionCode]` | `[]` | Generated code examples |
| `generated_at` | `datetime` | `now()` | Generation timestamp |

### QualityIssue

Location: `domain/entities/quality_report.py`

| Field | Type | Description |
|---|---|---|
| `section_id` | `str` | Which section has the issue |
| `issue_type` | `str` | Category of issue |
| `description` | `str` | Human-readable description |
| `severity` | `"error" \| "warning"` | Severity level |

### QualityReport

Location: `domain/entities/quality_report.py`
Pipeline role: **Node 6 output** - validation results.

| Field | Type | Default | Description |
|---|---|---|---|
| `passed` | `bool` | required | Whether the textbook passes quality check |
| `issues` | `list[QualityIssue]` | `[]` | Found issues |
| `checked_at` | `datetime` | `now()` | Check timestamp |

---

## Application DTOs

### GenerationRequest

Location: `application/dtos/generation_request.py`

Per-generation request fields (`subject`, `context`, optional depth/language overrides) plus `provider: str`. Student-level context is merged from the persistent `StudentProfile` by the use case.

### GenerationResponse

Location: `application/dtos/generation_request.py`

| Field | Type | Description |
|---|---|---|
| `textbook_id` | `str` | Unique identifier |
| `output_path` | `str` | Path to generated HTML |
| `quality_report` | `QualityReport \| None` | Quality check results |
| `generation_time_seconds` | `float` | Total generation time |

### GenerationStatus

Location: `application/dtos/generation_status.py`

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Generation job ID |
| `status` | `"pending" \| "running" \| "completed" \| "failed"` | Current status |
| `progress` | `GenerationProgress \| None` | Pipeline progress info |
| `result` | `GenerationResponse \| None` | Final result if completed |
| `error` | `str \| None` | Error message if failed |

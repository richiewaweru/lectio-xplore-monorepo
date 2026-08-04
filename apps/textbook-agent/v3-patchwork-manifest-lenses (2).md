# v3 Patchwork — Feed Manifest and Lenses to Lesson Architect

## What and why

The Lesson Architect currently uses `ARCHITECT_SYSTEM` — a bare string
constant with hardcoded placeholder component slugs. It has no knowledge
of what Lectio components actually exist.

Two files already in `backend/contracts/` contain what it needs:

- `manifest.json` — components grouped by pedagogical phase with `id`,
  `role`, `cognitiveJob`, `capabilities`, `section_field`
- `component-schemas.json` — not needed by the architect (goes to
  section writer via existing `get_field_schema()`)

The patch: replace the static string with a builder function that loads
`manifest.json` and appends the lens library.

---

## Files changed

```
backend/src/pipeline/contracts.py          ← add _load_manifest()
backend/src/generation/v3_studio/prompts.py ← replace ARCHITECT_SYSTEM
backend/src/generation/v3_studio/agents.py  ← use build_architect_system_prompt()
backend/resources/lenses/lesson/           ← 5 new YAML files
backend/resources/lenses/support/          ← 3 new YAML files
backend/src/v3_lenses/schema.py            ← new
backend/src/v3_lenses/loader.py            ← new
```

---

## Task 1 — Add manifest loader to pipeline/contracts.py

Same pattern as `_load_component_registry()`. Add after the existing loaders:

```python
@lru_cache(maxsize=None)
def _load_manifest() -> dict:
    path = _contracts_dir() / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(
            "manifest.json not found. "
            "Run: uv run python tools/update_lectio_contracts.py"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def get_manifest() -> dict:
    return _load_manifest()
```

---

## Task 2 — Write lens schema and loader

**`backend/src/v3_lenses/schema.py`:**

```python
from __future__ import annotations
from pydantic import BaseModel
from typing import Literal


class LensSchema(BaseModel):
    id: str
    label: str
    category: Literal["lesson", "support"]
    applies_when: str
    reasoning_principles: list[str]
    blueprint_effects: dict[str, str]
    principles: dict[str, str]
    avoid: list[str] = []
    conflicts_with: list[str] = []
```

**`backend/src/v3_lenses/loader.py`:**

```python
from __future__ import annotations
import logging
from functools import lru_cache
from pathlib import Path
import yaml
from v3_lenses.schema import LensSchema

logger = logging.getLogger(__name__)
_LENSES_DIR = Path(__file__).parents[2] / "resources" / "lenses"


@lru_cache(maxsize=1)
def _load() -> dict[str, LensSchema]:
    registry: dict[str, LensSchema] = {}
    for path in sorted(_LENSES_DIR.rglob("*.yaml")):
        with path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        lens = LensSchema.model_validate(raw)
        registry[lens.id] = lens
        logger.info("Loaded lens: %s", lens.id)
    if not registry:
        raise RuntimeError(f"No lenses found in {_LENSES_DIR}")
    return registry


def get_all_lenses() -> list[LensSchema]:
    return list(_load().values())
```

---

## Task 3 — Write the 8 lens YAML files

**`backend/resources/lenses/lesson/first_exposure.yaml`:**
```yaml
id: first_exposure
label: First Exposure
category: lesson
applies_when: >
  The learner has no working model of this concept.
  Genuine first teaching, not review.
reasoning_principles:
  - Create need before formal explanation
  - Use one stable anchor example throughout
  - Model before independent practice
  - Move warm to medium before attempting cold
  - Never ask a learner to practise what they have not first understood
blueprint_effects:
  visual_density: medium_or_high
  practice_progression: warm_to_medium
  vocabulary_policy: define_first
  anchor_reuse: entire_resource
  cold_questions: avoid_for_below_average
principles:
  anchor: >
    Choose one concrete example and reuse it everywhere.
    Familiarity before variation.
  sequence: >
    orient → explain → model → practise. Not negotiable.
  difficulty: >
    Warm uses anchor with minimal variation. Medium introduces one new dimension.
    No cold for below-average on first exposure.
avoid:
  - assuming prior fluency
  - starting with cold or transfer questions
  - different examples across explanation and practice
conflicts_with:
  - consolidation
  - transfer
```

**`backend/resources/lenses/lesson/consolidation.yaml`:**
```yaml
id: consolidation
label: Consolidation
category: lesson
applies_when: >
  The learner has a working model from prior teaching.
  Goal is fluency, not introduction.
reasoning_principles:
  - Use different examples from the original teaching lesson
  - Start at medium difficulty, not warm
  - Reach cold and transfer — that is the consolidation goal
  - One worked example maximum
  - Full working in the answer key
blueprint_effects:
  practice_progression: medium_to_cold
  worked_examples: minimal
  anchor_reuse: teaching_sequence_only
  answer_key_style: full_working
principles:
  examples: Different examples from original teaching. Transfer requires unfamiliarity.
  difficulty: Start medium. Cold and transfer are the target.
avoid:
  - re-teaching the concept from scratch
  - using the same examples as the original teaching lesson
  - starting with warm unless learner signals are very weak
conflicts_with:
  - first_exposure
  - repair
```

**`backend/resources/lenses/lesson/repair.yaml`:**
```yaml
id: repair
label: Repair
category: lesson
applies_when: >
  The learner has a specific misconception or gap.
  Taught before but something went wrong.
reasoning_principles:
  - Target the fault line only — not the whole concept again
  - Different approach and different example from original teaching
  - Tight practice set targeting only the misconception
  - Exit check required to confirm repair worked
  - Do not broaden scope under any circumstances
blueprint_effects:
  scope: fault_line_only
  examples: different_from_original
  exit_check: required
  visual_strategy: concrete_before_symbolic
principles:
  fault_line: Address only what specifically went wrong.
  approach: >
    Different visual or concrete approach from what failed.
    If original used symbolic notation, use a diagram first.
  practice: Questions target only the misconception.
avoid:
  - reteaching the whole concept
  - using the same approach as the original failed lesson
  - broad practice beyond the fault line
conflicts_with:
  - consolidation
  - first_exposure
```

**`backend/resources/lenses/lesson/retrieval.yaml`:**
```yaml
id: retrieval
label: Retrieval Practice
category: lesson
applies_when: >
  Learner encountered this concept in a prior lesson (spaced from now).
  Goal is recall and confidence, not new content.
reasoning_principles:
  - Low stakes — this is not assessment
  - Short and focused
  - No new anchor example needed
  - Confidence building before next new concept
blueprint_effects:
  resource_length: short
  visual_density: low
  practice_progression: warm_to_medium
  anchor_reuse: none
principles:
  tone: Low pressure. Frame as practice, not test.
avoid:
  - introducing new content
  - cold or transfer questions
  - heavy explanation blocks
conflicts_with: []
```

**`backend/resources/lenses/lesson/transfer.yaml`:**
```yaml
id: transfer
label: Transfer
category: lesson
applies_when: >
  Learner is fluent. Goal is applying the concept in novel real-world contexts.
reasoning_principles:
  - No scaffolding — learner works independently
  - Novel contexts — nothing from teaching or consolidation
  - Cold and extension questions only
  - Real-world application is the target
blueprint_effects:
  practice_progression: cold_to_transfer
  scaffolding: none
  visual_density: low
  anchor_reuse: none
principles:
  novelty: Context must be genuinely unfamiliar.
  independence: No worked examples. No hints.
avoid:
  - warm or medium questions
  - scaffolding of any kind
  - familiar examples from earlier in the unit
conflicts_with:
  - first_exposure
  - repair
```

**`backend/resources/lenses/support/high_load.yaml`:**
```yaml
id: high_load
label: High Cognitive Load Support
category: support
applies_when: >
  ADHD, dyslexia, below-grade reading, low confidence.
reasoning_principles:
  - One idea per component — never combine explanation and example in one block
  - Visual before text where possible
  - More worked examples before independent practice
  - Short sentences, active voice, concrete before abstract
  - Warm questions heavily scaffolded
blueprint_effects:
  chunking: one_idea_per_component
  visual_density: high
  vocabulary_policy: define_first
  practice_progression: warm_only_or_warm_to_medium
  register: simple
principles:
  chunking: Break content into smallest possible units.
  register: Short sentences. No passive voice. Define every term.
avoid:
  - dense prose explanation blocks
  - cold questions in a first exposure lesson for this group
  - idiom or figurative language
```

**`backend/resources/lenses/support/eal.yaml`:**
```yaml
id: eal
label: EAL Support
category: support
applies_when: >
  English as an additional language learners, or multilingual classroom.
reasoning_principles:
  - High visual density — images reduce language dependency
  - DefinitionCard for every key term before first use
  - No idiom, no cultural references requiring local knowledge
  - Label every diagram element explicitly
  - Mathematical language over everyday language where both work
blueprint_effects:
  visual_density: high
  vocabulary_policy: define_first
  labels_required: explicit_on_all_diagrams
  register: plain_and_precise
principles:
  vocabulary: Every technical term gets a definition before it appears.
  visual: More diagrams than a standard lesson.
  language: Avoid idiom. Prefer precise mathematical language.
avoid:
  - idiom or culturally-specific examples
  - assuming academic vocabulary
  - dense prose without visual support
```

**`backend/resources/lenses/support/advanced.yaml`:**
```yaml
id: advanced
label: Advanced Learners
category: support
applies_when: >
  Above-grade, high confidence, analytical learners.
reasoning_principles:
  - Compress scaffolding — one worked example maximum
  - Formal register, precise terminology
  - Reach cold and transfer questions
  - Include at least one open-ended or proof-adjacent question
  - No hand-holding preamble
blueprint_effects:
  worked_examples: maximum_one
  practice_progression: medium_to_transfer
  register: formal
  scaffolding: minimal
principles:
  pace: Skip or compress warm questions.
  register: Formal, precise language from the first sentence.
  challenge: Cold or transfer question is where advanced learners engage.
avoid:
  - excessive scaffolding
  - warm questions unless concept is genuinely new
  - informal or simplified language
```

---

## Task 4 — Replace ARCHITECT_SYSTEM with builder in prompts.py

Remove the `ARCHITECT_SYSTEM` constant. Add the builder function:

```python
from functools import lru_cache
from pipeline.contracts import get_manifest
from v3_lenses.loader import get_all_lenses


@lru_cache(maxsize=1)
def _manifest_block() -> str:
    """
    Extract only what the Lesson Architect needs for planning.
    Four fields per component, one line each:
      id [section_field]: role — cognitiveJob

    Deliberately excludes: print, capacity, shadcn_primitive,
    behaviour_modes, subjects, capabilities.
    Those are executor-layer concerns, not planning concerns.
    """
    manifest = get_manifest()
    lines = ["AVAILABLE COMPONENTS (use only these slugs):"]
    for phase_id, phase in manifest["phases"].items():
        lines.append(f"\nPhase {phase_id} — {phase['name']}:")
        for c in phase["components"]:
            slug = c["id"]
            section_field = c.get("section_field") or "—"
            role = c.get("role", "")
            cognitive_job = c.get("cognitive_job", "")
            lines.append(
                f"  {slug} [{section_field}]: {role} — {cognitive_job}"
            )
    return "\n".join(lines)


@lru_cache(maxsize=1)
def _lens_block() -> str:
    lines = ["\nPEDAGOGICAL LENSES (apply those that fit the signals):"]
    for lens in get_all_lenses():
        lines.append(f"\n  {lens.id} ({lens.label}):")
        lines.append(f"  When: {lens.applies_when.strip()}")
        for principle in lens.reasoning_principles[:3]:
            lines.append(f"  - {principle}")
    return "\n".join(lines)


def build_architect_system_prompt() -> str:
    return f"""You are a lesson architect. Output ONLY a valid ProductionBlueprint matching the schema.

{_manifest_block()}
{_lens_block()}

Rules:
- Only use component slugs listed above. Never invent slugs.
- metadata: version "3.0", title, subject
- lesson: lesson_mode first_exposure|consolidation|repair|retrieval|transfer
- applied_lenses: min 1 lens, lens_id must match a lens above, effects non-empty
- voice: register simple|balanced|formal, optional tone
- anchor: reuse_scope string
- sections: min 1, each section_id, title, role, visual_required bool,
  components (slugs from above) with content_intent
- question_plan: min 1, each question_id, section_id,
  temperature warm|medium|cold|transfer, prompt, expected_answer, diagram_required
- visual_strategy: visuals list for sections where visual_required=true
- answer_key: style e.g. concise_steps or answers_only
"""
```

---

## Task 5 — Update agents.py

```python
# Remove this import:
from generation.v3_studio.prompts import ARCHITECT_SYSTEM

# Add this import:
from generation.v3_studio.prompts import build_architect_system_prompt

# In generate_production_blueprint(), change:
agent = Agent(
    model=model,
    output_type=ProductionBlueprintEnvelope,
    system_prompt=build_architect_system_prompt(),  # was ARCHITECT_SYSTEM
)
```

---

## Implementation order

```
1. Task 1 — add get_manifest() to pipeline/contracts.py
2. Task 2 — write v3_lenses/schema.py and loader.py
3. Task 3 — write all 8 YAML files under resources/lenses/
4. Task 4 — replace ARCHITECT_SYSTEM with build_architect_system_prompt()
5. Task 5 — update agents.py
```

Tasks 2 and 3 can run in parallel. Task 4 depends on Tasks 1, 2, 3.
Task 5 depends on Task 4.

---

## Verification

```
□ get_manifest() returns non-empty dict — at least 10 component entries
□ get_all_lenses() returns 8 LensSchema instances without error
□ build_architect_system_prompt() contains real component slugs from manifest
□ build_architect_system_prompt() contains all 8 lens ids
□ agents.py no longer references ARCHITECT_SYSTEM constant
□ Blueprint from a real brief contains only valid manifest slugs
□ Blueprint from an EAL + first exposure brief includes eal and
  first_exposure in applied_lenses
```

---

# Addendum — Lean Manifest Extraction

## Why this patch exists

The raw `manifest.json` includes per-component fields the Lesson Architect
never uses: `print`, `capacity`, `shadcn_primitive`, `behaviour_modes`,
`subjects`, `capabilities`. Feeding these to Opus wastes context window,
increases input token cost on every blueprint request, and dilutes the
prompt with execution-layer noise that competes with the pedagogical
reasoning that actually matters.

The `_manifest_block()` function already does extraction. This patch
locks in the exact four fields that serve the planning job and documents
why everything else is excluded.

---

## The extraction rule

One line per component:

```
{id} [{section_field}]: {role} — {cognitiveJob}
```

**`id`** — the slug the architect writes into the blueprint `components`
list. The executor reads this to know which Lectio component to generate
content for.

**`section_field`** — the `SectionContent` key this component maps to.
The architect needs this as a constraint: two components that share the
same `section_field` cannot both appear in the same section or they
silently collide at assembly time. Knowing the field at planning time
prevents the blueprint from creating that conflict.

**`role`** — what the component is pedagogically for. The architect
reads this to decide whether this component serves the current lesson
stage.

**`cognitiveJob`** — the cognitive demand it creates in the learner.
The architect reads this to sequence components correctly — you don't
follow a `recall` component with another `recall`, you follow it with
`apply` or `evaluate`.

**Excluded and why:**
```
print           → executor concern — how the component renders in print
capacity        → executor concern — word/item limits per field
shadcn_primitive → rendering concern — UI component used internally
behaviour_modes → rendering concern — static/interactive variants
subjects        → too broad to guide planning decisions
capabilities    → executor concern — acceptsMedia, producesAnswerKey etc
```

---

## What the extracted manifest looks like

For a handful of components it produces:

```
AVAILABLE COMPONENTS (use only these slugs):

Phase 1 — Orient:
  hook-hero [hook]: Opens the lesson with a compelling real-world need — Create desire to learn
  section-header [header]: Named visual break and title — Signal structure
  what-next-bridge [what_next]: Closes a section with forward momentum — Anticipate next step

Phase 2 — Build Knowledge:
  explanation-block [explanation]: Sustained prose that builds a mental model — Build understanding
  definition-card [definition]: Isolates and defines a single term precisely — Lock in vocabulary
  key-fact [key_fact]: Surfaces one critical fact for emphasis — Anchor a key claim

Phase 3 — Demonstrate Method:
  worked-example-card [worked_example]: Step-by-step method applied to a concrete problem — See the process
  process-steps [process]: Numbered procedure for a repeatable task — Follow a sequence

Phase 4 — Practice and Check:
  practice-stack [practice]: Set of graded practice problems — Apply independently
  quiz-check [quiz]: Low-stakes comprehension check — Verify recall
```

Opus reads this in one pass. No noise. Every slug has its planning
purpose visible at a glance. The `section_field` in brackets gives
the constraint the architect needs to avoid collisions.

---

## The section_field collision rule

Add this line to `build_architect_system_prompt()` after the component
list:

```python
"""
CONSTRAINT: Each section_field may appear at most once per section.
Two components sharing the same section_field cannot both be planned
for the same section. Check the field in brackets before adding a
component to a section.
"""
```

This is a deterministic rule the architect can apply mechanically.
It prevents the most common blueprint validity error without requiring
the coherence reviewer to catch it downstream.

---

## File change summary

Only `backend/src/generation/v3_studio/prompts.py` changes. The
`_manifest_block()` function is already in the previous patch — this
addendum clarifies the extraction rationale and adds the collision
constraint to `build_architect_system_prompt()`.

**Updated `build_architect_system_prompt()`:**

```python
def build_architect_system_prompt() -> str:
    return f"""You are a lesson architect. Output ONLY a valid ProductionBlueprint matching the schema.

{_manifest_block()}

CONSTRAINT: Each section_field (shown in brackets above) may appear at
most once per section. Never plan two components with the same
section_field in the same section.

{_lens_block()}

Rules:
- Only use component slugs listed above. Never invent slugs.
- metadata: version "3.0", title, subject
- lesson: lesson_mode first_exposure|consolidation|repair|retrieval|transfer
- applied_lenses: min 1 lens, lens_id must match a lens above, effects non-empty
- voice: register simple|balanced|formal, optional tone
- anchor: reuse_scope string
- sections: min 1, each section_id, title, role, visual_required bool,
  components (slugs from above) with content_intent
- question_plan: min 1, each question_id, section_id,
  temperature warm|medium|cold|transfer, prompt, expected_answer, diagram_required
- visual_strategy: visuals list for sections where visual_required=true
- answer_key: style e.g. concise_steps or answers_only
"""
```

---

## Verification additions

```
□ _manifest_block() output contains no mention of print, capacity,
  shadcn_primitive, behaviour_modes, subjects, or capabilities
□ Each component line has exactly the format: slug [field]: role — job
□ build_architect_system_prompt() includes the section_field collision rule
□ Blueprint from a 5-section lesson has no two components sharing
  the same section_field within any single section
```

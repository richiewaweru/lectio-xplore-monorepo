# ResourceType Enum — Correction Note

**Affects:** `architect-stability-improvements.md` → Issue 1  
**Status:** Superseded by this document. Do not use the stability doc's ResourceType values.

---

## The conflict

Three documents written during the same planning session produced three different `ResourceType` sets. None of them matched what was actually on disk.

| Source | Values declared |
|---|---|
| `architect-stability-improvements.md` (Issue 1) | `lesson`, `mini_booklet`, `quiz`, `retrieval_practice`, `worked_example_set` |
| `merged-architect-prompt.md` (Step 4 SIGNAL_SYSTEM) | `lesson`, `mini_booklet`, `worksheet`, `quiz`, `exit_ticket`, `practice_set`, `quick_explainer` |
| `backend/resources/specs/` on disk (ground truth) | `mini_booklet`, `worksheet`, `exit_ticket`, `quick_explainer`, `practice_set`, `quiz` |

The ground truth is the test at `backend/tests/resource_specs/test_loader.py`:

```python
def test_all_resource_specs_load() -> None:
    specs = load_all_specs(SPECS_DIR)
    assert set(specs) == {
        "mini_booklet",
        "worksheet",
        "exit_ticket",
        "quick_explainer",
        "practice_set",
        "quiz",
    }
```

These six IDs are what `get_spec()` can actually serve. Anything outside this set causes `_render_resource_spec()` to fall back to a generic message, meaning the architect receives no structural guidance for that resource type.

---

## What was wrong in the stability document

`retrieval_practice` and `worked_example_set` were invented during planning. No spec YAML files exist for them. Adding them to the Pydantic enum without backing specs means:

- The architect can produce blueprints with `resource_type: "retrieval_practice"`
- `_render_resource_spec()` silently falls back — the architect gets no forbidden components, no section rules, no depth limits
- The resource spec gate (STEP 3 of the reasoning scaffold) becomes a no-op for those types
- QC has no structural contract to validate against

This is exactly the kind of drift the resource spec system was designed to prevent.

---

## The correct `ResourceType` enum

```python
ResourceType = Literal[
    "lesson",           # fallback only — no spec file; architect uses judgment
    "mini_booklet",     # full guided lesson with scaffolding (spec exists)
    "worksheet",        # practice resource; concept already taught (spec exists)
    "quiz",             # formal assessment (spec exists)
    "exit_ticket",      # short end-of-lesson check (spec exists)
    "practice_set",     # drill-style repetition (spec exists)
    "quick_explainer",  # focused concept clarification (spec exists)
]
```

`lesson` is kept as a fallback only. It has no spec file. When the signal extractor infers `lesson`, `_render_resource_spec()` returns a generic message and the architect plans from judgment. This is acceptable as a default.

---

## The correct `SIGNAL_SYSTEM` resource type list

```python
SIGNAL_SYSTEM = """You extract structured teaching signals from a structured teacher form.

The form already provides lesson_mode, learner_level, support_needs, prior_knowledge_level,
intended_outcome, grade_level, subject, duration_minutes, topic, and subtopics.

Do NOT re-infer these from free text. Read them directly from the form fields.

Your job:
- Confirm the teaching topic (short, specific).
- Optionally select ONE subtopic string (or null) if the form subtopics are empty or too broad.
- Summarise teacher_goal in one clear sentence.
- Set inferred_resource_type to one of:
    lesson          — default; full instructional lesson with explanation and practice
    mini_booklet    — compact guided learning students can follow step by step
    worksheet       — practice resource; concept has already been taught
    quiz            — formal assessment with scored questions
    exit_ticket     — short end-of-lesson check, 3–5 questions
    practice_set    — drill-style repetition, minimal explanation
    quick_explainer — focused concept clarification or reference card
  Default to lesson if the teacher's intent does not clearly match another type.
- Populate missing_signals ONLY if topic is genuinely ambiguous or contradictory.
"""
```

---

## On aliases — why not to collapse types

During planning the following aliases were proposed:

```
practice_set     → retrieval_practice (if recall-heavy)
quick_explainer  → lesson with shallow depth
```

Do not implement these. `practice_set` and retrieval practice are meaningfully different:

- `practice_set` (`practice_set.yaml`): deliberate application of a concept that was taught; warm-to-cold progression; explanation is assumed to have happened elsewhere
- Retrieval practice: low-cue recall with intentional forgetting; no explanation; cold questions from the start

Collapsing them as aliases loses the structural distinction that the spec files encode. `quick_explainer` already has its own spec with its own section rules — routing it to `lesson` bypasses those rules.

---

## CI guard — add this test to prevent future drift

Add to `backend/tests/resource_specs/test_loader.py`:

```python
def test_resource_type_enum_matches_available_specs() -> None:
    """
    ResourceType in v3_blueprint/models.py must contain exactly the spec IDs
    that exist on disk, plus 'lesson' as the fallback (no spec file).

    Fails if:
    - A spec YAML was added but ResourceType was not updated, OR
    - A ResourceType value was added with no backing spec YAML.
    Fix by keeping the enum and spec files in sync.
    """
    from v3_blueprint.models import ResourceType

    spec_ids = set(load_all_specs(SPECS_DIR).keys())
    enum_values = set(ResourceType.__args__) - {"lesson"}

    in_enum_not_in_specs = enum_values - spec_ids
    in_specs_not_in_enum = spec_ids - enum_values

    assert not in_enum_not_in_specs, (
        f"ResourceType contains values with no backing spec YAML: "
        f"{sorted(in_enum_not_in_specs)}. "
        f"Add a spec YAML for each, or remove from ResourceType."
    )
    assert not in_specs_not_in_enum, (
        f"Spec YAMLs exist with no matching ResourceType value: "
        f"{sorted(in_specs_not_in_enum)}. "
        f"Add them to ResourceType in v3_blueprint/models.py."
    )
```

This test makes the enum self-enforcing. Any developer who adds a spec YAML without updating the enum (or vice versa) gets an immediate CI failure with a message pointing at exactly what drifted.

---

## If you want to add `retrieval_practice` or `worked_example_set` in the future

The correct sequence is:

1. Write the spec YAML (`backend/resources/specs/retrieval_practice.yaml`)
2. Confirm `test_all_resource_specs_load()` fails (it will, until the enum is updated)
3. Add the value to `ResourceType` in `v3_blueprint/models.py`
4. Confirm `test_resource_type_enum_matches_available_specs()` passes
5. Add the type to `SIGNAL_SYSTEM` in `prompts.py`

The spec YAML is the gate. The enum follows the spec. Never the other way around.

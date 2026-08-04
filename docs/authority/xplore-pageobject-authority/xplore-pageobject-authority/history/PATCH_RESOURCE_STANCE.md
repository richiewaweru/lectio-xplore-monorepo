> HISTORICAL INPUT — NOT IMPLEMENTATION AUTHORITY

# PATCH — Resource Stance

**Applies to:** `BUILD_GOAL.md` phases 4, 6, 7, 10
**Reason:** the selectors currently have no idea what resource they are building.

---

## The problem

The Step 1 and Step 2 prompts receive slot purpose, candidate intents, objective,
misconceptions, and prior knowledge. They receive nothing that says *this is a
worksheet*. A model choosing between `practise-guided` and `apply` is doing it
blind to whether it is writing a lesson, a worksheet, or an exit ticket.

The `vocabulary` block encodes what a resource may *contain*. It does not encode
what a resource *is*. Those are different, and only the first one landed.

The existing `intent:` prose in each spec is written for a human reader. Read as
a block-level decision rule it evaporates — "a worksheet is a practice resource,
the teacher has already taught the concept" is true and changes nothing about
which intent to pick, because the exclusion list already said that.

## The fix

Add `stance`: four fields, each a test the model can apply to its own output
rather than a description it can nod along to.

```
identity          which resource, by name and id — stated, not inferred
student_arrives_with   what the reader already holds
page_is_spent_on       what the page budget is for
reader_is              reading | writing | checking | revising
fails_by               the characteristic failure of this resource type
```

`reader_is` does the most quiet work. `reading` versus `writing` changes block
length, prose density, and whether a table is a reference or something to fill
in — across every intent, without naming any of them.

---

## 1. Schema — `backend/src/resource_specs/schema.py`

Add to phase 4.

```python
from typing import Literal


class StanceSpec(BaseModel):
    """What this resource IS, as tests a writer can apply.

    Distinct from `vocabulary`, which says what a resource may contain.
    Distinct from `intent`, which is prose for a human reader.
    """

    model_config = ConfigDict(extra="ignore")

    student_arrives_with: str = Field(
        default="",
        description="What the reader already holds when they pick this up.",
    )
    page_is_spent_on: str = Field(
        default="",
        description="What the page budget buys. What every block must serve.",
    )
    reader_is: Literal["reading", "writing", "checking", "revising"] = Field(
        default="reading",
        description="The reader's dominant activity. Governs block length, "
        "prose density, and whether tasks need answer space.",
    )
    fails_by: str = Field(
        default="",
        description="The characteristic failure of this resource type. "
        "The single most useful line in the block.",
    )
```

On `ResourceSpec`, add:

```python
    stance: StanceSpec = Field(default_factory=StanceSpec)
```

Defaults everywhere, so the five unmigrated specs still load.

**Add a rendering helper** — `backend/src/resource_specs/renderer.py`:

```python
def render_stance_for_prompt(spec: ResourceSpec) -> str:
    """Resource identity block. Emitted at the TOP of both selector prompts,
    before candidates, so it frames the decision rather than qualifying it.
    """
    s = spec.stance
    return "\n".join(
        [
            "## THE RESOURCE YOU ARE BUILDING",
            "",
            f"  Resource:        {spec.label} ({spec.id})",
            f"  Student arrives: {s.student_arrives_with.strip()}",
            f"  Page spent on:   {s.page_is_spent_on.strip()}",
            f"  Reader is:       {s.reader_is}",
            f"  Fails by:        {s.fails_by.strip()}",
            "",
            "Every choice below serves this resource. A choice that would be",
            "correct in a different resource type is wrong here.",
        ]
    )
```

Do **not** write a second renderer. `render_spec_for_prompt` already exists;
this sits beside it and both selector prompt builders call it.

---

## 2. `backend/resources/specs/lesson.yaml`

Insert directly after `allowed_outcomes:` and before `vocabulary:`.

```yaml
# ── STANCE (v2) ─────────────────────────────────────────────────────────────
# What this resource IS. Emitted at the top of every selector prompt so the
# model knows which artifact it is building before it chooses anything.

stance:
  student_arrives_with: >
    Nothing about this concept. This is first contact. Assume only the
    prerequisites named in the path, and nothing about the idea itself.

  page_is_spent_on: >
    Building one idea until the learner can use it on a case they have not
    seen. Every block either builds that idea, models its use, or checks it.

  reader_is: reading

  fails_by: >
    Skipping the modelling step, or turning the close into a second teaching
    section. If a learner could have reached the practice blocks without the
    blocks before them, the arc has collapsed and the lesson is a worksheet
    with an introduction.
```

---

## 3. `backend/resources/specs/worksheet.yaml`

Same position — after `allowed_outcomes:`, before `vocabulary:`.

```yaml
# ── STANCE (v2) ─────────────────────────────────────────────────────────────

stance:
  student_arrives_with: >
    The concept, taught. They hold the idea and need to use it. Anything that
    re-establishes what they already have is wasted page and wasted minutes.

  page_is_spent_on: >
    The student's working. Text exists to set up a task, never to carry an
    idea. If the student is reading for more than a third of the time, this
    resource has failed on its own terms.

  reader_is: writing

  fails_by: >
    Re-teaching. If a block would be equally at home in the lesson that
    preceded this worksheet, it does not belong here. The second failure is
    flatness — problems that do not move from supported to unsupported are a
    drill, not a worksheet.
```

---

## 4. `intent-selector-v1.txt`

Three edits. The file is otherwise unchanged.

### 4a. New section, immediately after the opening four lines

Insert before `## WHAT YOU ARE GIVEN`:

```
## THE RESOURCE YOU ARE BUILDING

This block is filled from the resource spec and appears above every decision
you make. Read it first.

  Resource:        {label} ({id})
  Student arrives: {student_arrives_with}
  Page spent on:   {page_is_spent_on}
  Reader is:       {reader_is}
  Fails by:        {fails_by}

Every choice below serves this resource. A teaching move that would be correct
in a different resource type is wrong here, however well it fits the slot.

Reader is: writing means the page belongs to the student's pen. Reader is:
reading means the page belongs to the idea. This changes what a good block is
before you consider a single candidate.
```

### 4b. New paragraph inside `## HOW TO CHOOSE`

Append after the worked decision, before `## THE EVIDENCE RULE`:

```
Before you commit, hold the choice against fails_by.

  Resource: worksheet
  fails_by: re-teaching

    A block that establishes the idea is the named failure of this resource,
    even when the slot purpose sounds like it wants one and even when the
    intent is in candidate_intents. Choose the move that puts the student
    to work.

fails_by is not a warning. It is a rejection test, and it outranks a
candidate's choose_when.
```

### 4c. Two new self-check lines

```
  6. Would this intent be at home in a different resource type? If yes,
     re-read fails_by.
  7. If the reader is writing, does my brief put the student to work, or
     does it explain first?
```

---

## 5. `object-selector-v1.txt`

Three edits.

### 5a. Same identity block

Insert before `## WHAT YOU ARE GIVEN`, with the closing lines changed:

```
## THE RESOURCE YOU ARE BUILDING

  Resource:        {label} ({id})
  Student arrives: {student_arrives_with}
  Page spent on:   {page_is_spent_on}
  Reader is:       {reader_is}
  Fails by:        {fails_by}

The teaching job is fixed. The form still has to suit this resource.
```

### 5b. New section after `## THE DEFAULT IS PROSE`

```
## READER IS

reader_is governs how much of the page the reader may spend on text.

  reading    the page belongs to the idea. prose may run to its capacity.
             a table is a reference the reader consults.

  writing    the page belongs to the student's pen. prose is a setup line,
             not a paragraph. a table is something to fill in, and must
             have blank cells. questions need answer space, and that space
             is part of the object, not an afterthought.

  checking   short stems, unambiguous tasks, no scaffolding in the wording.

  revising   compressed. tables and lists over prose. nothing to fill in.

A prose block of four paragraphs is correct when the reader is reading and
wrong when the reader is writing, with the same intent and the same brief.
```

### 5c. Two new self-check lines

```
  6. Does this object suit reader_is, not just the intent?
  7. If the reader is writing, does this object leave room to write? A table
     the student cannot fill is a reference, not a task.
```

---

## 6. `selector_dryrun.py` — phase 10

Add to the prompt rendering rules:

```
- Both prompts open with render_stance_for_prompt(spec). It is the FIRST
  content after the prompt file's own preamble, before candidates and before
  objective. Identity frames the decision; it does not qualify it afterwards.

- Include spec.label and spec.id verbatim. The model should be able to name
  the artifact it is producing. Do not paraphrase "Practice Worksheet" into
  "worksheet" or drop the id.

- reader_is is passed as the bare enum value, not a sentence. The prompt
  file supplies the meaning; the spec supplies the value.
```

Add to the dry-run output table so a human can see identity was passed:

```
RESOURCE | READER | SLOT | INTENT | EVIDENCE | OBJECT | REASON | BRIEF
```

---

## 7. Tests

Add to phase 8, `test_spec_skeleton_pairs.py`:

```python
def test_migrated_specs_declare_stance():
    """A v2 spec without a stance gives the selector no resource identity."""
    for spec_id in ("lesson", "worksheet"):
        spec = get_spec(spec_id)
        s = spec.stance
        assert s.student_arrives_with.strip(), f"{spec_id}: stance.student_arrives_with empty"
        assert s.page_is_spent_on.strip(), f"{spec_id}: stance.page_is_spent_on empty"
        assert s.fails_by.strip(), f"{spec_id}: stance.fails_by empty"


def test_stance_renders_into_prompts():
    """Identity must reach the prompt, not just the model."""
    spec = get_spec("worksheet")
    block = render_stance_for_prompt(spec)
    assert "Practice Worksheet" in block
    assert "worksheet" in block
    assert "writing" in block
    assert spec.stance.fails_by.split()[0] in block
```

The second test exists because this whole patch is a fix for information that
was declared and never passed through. A test that only checks the YAML would
have passed while the bug was live.

---

## 8. Deltas to `BUILD_GOAL.md`

| Phase | Change |
|---|---|
| 4 | add `StanceSpec`, `ResourceSpec.stance`, `render_stance_for_prompt` |
| 6 | add the stance block to `lesson.yaml` and `worksheet.yaml` |
| 7 | prompt files include the identity section and the new self-checks |
| 8 | two stance tests |
| 10 | stance renders first in both prompts; `RESOURCE` and `READER` columns |

No phase reordering. No new phase.

**Acceptance additions:**

```
[ ] StanceSpec on the schema, defaults so unmigrated specs still load
[ ] lesson.yaml and worksheet.yaml declare all four stance fields
[ ] render_stance_for_prompt exists in renderer.py, not a new module
[ ] both prompt files open with the resource identity block
[ ] --dry output shows RESOURCE and READER columns
[ ] test_stance_renders_into_prompts passes
```

---

## Note for the morning

The other five specs get `stance` when they get `vocabulary`. Writing a stance
is harder than writing a vocabulary list and worth more — `fails_by` in
particular forces a real statement about what the resource is for.

If a resource type cannot produce a distinct `fails_by`, that is evidence it is
not a distinct resource type. Worth applying to `practice_set` versus
`worksheet` before writing either.

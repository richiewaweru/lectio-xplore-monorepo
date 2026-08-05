# Kickoff Addendum — Cutline 1.5: Prompts and Vocabulary

**Amends:** `xplore-whole-lesson-planning-implementation-kickoff.md`
**Authority:** `xplore-whole-lesson-planning-resolved-proposal-v1.1.md`
**Inserts between:** Cutline 1 (make planning honest) and Cutline 2 (produce
and approve the teaching plan)
**Estimate:** half a day. It gates everything after it.

---

## Why this exists

The kickoff brief specifies the plumbing precisely — DTOs, validation,
persistence, events, endpoints, figure lifecycle, print policy. It says almost
nothing about what goes inside the two model calls.

Cutline 2 lists "standard-tier agent" as an implementation item, as though the
prompt already exists. It does not. Neither does the form planner's. And three
prompt files currently in the repository encode the per-slot design that v1.1
replaces.

Prompts are where the quality lives. Two thousand lines of correct plumbing
around a vague planner prompt produces a correctly persisted, fully validated,
beautifully rendered mediocre lesson.

---

## 1. Delete

```
backend/resources/section-block-planner-v1.txt
backend/resources/component-selector-v1.txt
```

`section-block-planner-v1.txt` encodes per-slot planning — the design v1.1
removes. Leaving it in the tree invites someone to wire it back.

`component-selector-v1.txt` belongs to the v1 path. If v1 generation must keep
running during migration, keep the file and mark it `# v1 ONLY — do not use on
the native path`. Otherwise delete it.

---

## 2. Resolve the misconception and anchor conflict

**This is a real conflict and it must be settled before either planner runs.**

`backend/resources/path-structural-planner-page-v1.txt` currently instructs:

> Draft zero to three real misconceptions. Each must support a confident wrong
> answer.
>
> Reuse the carried anchor when it fits. Otherwise choose one concrete anchor.

v1.1 §13 places anchor ownership upstream and passes it to the lesson planner
as fixed input. v1.1 §7.1 has the lesson planner emitting
`misconception_focus_ids` — a selection from an approved list, not a drafting
step.

So two prompts currently claim the same two decisions.

**Resolution — the structural planner keeps both, the lesson planner receives
them.**

```
STRUCTURAL PLANNER  (upstream, per lesson)
  drafts misconceptions        → approved, stored with IDs
  chooses / carries the anchor → stored with an ID
          │
          ▼
LESSON PACKET  (immutable)
  misconceptions[]  with IDs
  anchor            with ID
          │
          ▼
LESSON APPROACH PLANNER
  SELECTS which misconceptions to focus  (misconception_focus_ids)
  DECIDES how each section uses the anchor  (anchor_usage)
  may do neither of the drafting jobs
```

Why this way round: misconceptions must be stable across lesson variants and
must match the approved item pool, so drafting them inside a per-lesson
generation call would break both. The anchor carries forward across lessons in
a path — a generation call must not be able to discard that continuity.

**Edit required:** `path-structural-planner-page-v1.txt` keeps its
misconception and anchor sections unchanged. Add one line to its prohibitions:

```
- Never choose page blocks, intents, objects, or briefs. A later planner
  owns the teaching design.
```

---

## 3. Add

```
backend/resources/lesson-approach-planner-v1.txt     supplied
backend/resources/form-planner-v1.txt                supplied
```

Copy both verbatim. **Do not condense, reformat, or improve the wording.**
Every clause is deliberate. If something reads oddly, record it rather than
changing it — a prompt edited during implementation cannot be attributed when
Run 1's output is read.

Both files contain one substitution token:

```
{resource_identity}
```

See section 4.

Both are written against the v1.1 §7.1 output schema exactly. The teaching
planner emits `arc`, `anchor_usage`, `misconception_focus_ids`, and
`sections[].blocks[]` with `id`, `position`, `intent`, `brief`,
`evidence_refs`, `evidence`, `departure_reason`, `source_question_ids`. It does
not emit `from_typical` — that is computed by code per v1.1 §7.3.

---

## 4. Resource identity — no new schema object

An earlier draft proposed a `stance` object on the resource spec. **Rejected.**
The spec already states what the resource is, and adding a second place to say
it recreates the duplication this rewrite removes.

Add to `backend/src/resource_specs/renderer.py`:

```python
def render_resource_identity(spec: ResourceSpec) -> str:
    """Resource identity for planner prompts. Reads existing spec fields.
    Introduces no new schema."""
    lines = [f"  Resource: {spec.label} ({spec.id})", ""]
    lines += [f"  {line}" for line in spec.intent.strip().splitlines()]
    lines.append("")
    if spec.when_to_use:
        lines.append("  Use when:")
        lines += [f"    - {x}" for x in spec.when_to_use]
    if spec.never_use_when:
        lines.append("  Never when:")
        lines += [f"    - {x}" for x in spec.never_use_when]
    return "\n".join(lines)
```

Substituted into `{resource_identity}` in both planner prompts.

If the rendered identity reads weakly, **sharpen the prose in `lesson.yaml`.**
That is a text edit to an existing field, not a schema change.

---

## 5. Vocabulary rename — `candidate_intents` → `typical_intents`

The repository currently treats a slot's intents as a closed set:

```python
# planning/page_blocks.py
if block.intent not in allowed:
    raise PageBlockPlanError(f"intent {block.intent!r} not in closed candidates")
```

v1.1 replaces the fence with a wall plus a reason. Three tiers, not two:

```
excluded            hard wall. reject.
permitted           available. atypical use requires departure_reason.
typical_intents     what this slot usually needs. guidance, not a gate.
```

**Without this change the whole-lesson planner cannot depart from a slot's
usual intent, and the design silently does not happen.**

Changes:

| File | Change |
|---|---|
| `backend/resources/skeletons.yaml` | `candidate_intents:` → `typical_intents:` on all slots |
| `v3_blueprint/skeletons.py` | field rename on the slot model |
| `resource_specs/candidates.py` | returns `typical` / `permitted` / `excluded+reasons`; rename `resolve_block_candidates` → `assemble_lesson_guidance`, scoped to the whole lesson |
| `planning/page_blocks.py` | delete `plan_section_blocks`, `plan_conceptual_first_exposure_blocks`, `_fixture_plan_for_slot`, and the closed-set check |
| `lesson.yaml` vocabulary | `core` / `optional` → `permitted`. `excluded` unchanged and now genuinely load-bearing |

The closed-set assertion is replaced by the v1.1 §8.1 checks: intent is
permitted, no excluded intent appears, departure rules hold.

**Delete the empty-intersection CI test.** With no gate there is no empty set.
Configuration problems surface as departure-rate patterns instead, which is
better evidence anyway.

---

## 6. Writer prompts — input contract change

Five writer prompts exist and are kept. Their inputs change.

```
backend/resources/page-writer-common-v1.txt      shared preamble
backend/resources/prose-writer-v1.txt
backend/resources/list-writer-v1.txt
backend/resources/table-writer-v1.txt
backend/resources/worked-example-writer-v1.txt
backend/resources/figure-brief-writer-v1.txt
```

No writer prompt is needed for `questions` — assembly is deterministic and
must remain so.

Every writer now receives, and the common preamble must render:

```
LESSON CONTEXT
  objective, grade, terminology, must_not_introduce, anchor

THIS BLOCK — FIXED, NOT YOURS TO CHANGE
  block_id, position
  intent          + generation_guidance from the intent catalogue
  brief
  object          + content_schema + capacity from the object catalogue

NEIGHBOURS
  brief of the block before
  brief of the block after
```

Three additions to `page-writer-common-v1.txt`:

**Intent guidance.** The writer must receive `intent.generation_guidance`.
Without it, `aside` + `warn` and `aside` + `memory-aid` produce the same text.
Different job, same shape — the guidance is what separates them.

**Neighbour briefs.** Without them block 3 repeats block 2. Add:

```
The briefs before and after yours are shown so you do not repeat them and do
not leave a gap. Do not write their content. Do not refer to them as "the
previous section".
```

**Object names never appear in output.** The old components rendered their own
chrome; the renderer now does it. Add:

```
Never write the name of your object into the content. No "Worked example:",
no "Table showing...", no "Note:". The renderer supplies all labels.
```

---

## 7. Acceptance for this cutline

```
[ ] section-block-planner-v1.txt deleted
[ ] component-selector-v1.txt deleted or marked v1-only
[ ] path-structural-planner-page-v1.txt keeps misconceptions + anchor,
    gains the "never choose blocks or intents" prohibition
[ ] lesson-approach-planner-v1.txt present, byte-identical to supplied
[ ] form-planner-v1.txt present, byte-identical to supplied
[ ] render_resource_identity exists in resource_specs/renderer.py
[ ] {resource_identity} substitutes correctly in both prompts
[ ] typical_intents rename complete across yaml, model, and code
[ ] closed-set check removed; v1.1 §8.1 checks in its place
[ ] plan_section_blocks and the fixture planner deleted
[ ] empty-intersection CI test removed
[ ] page-writer-common-v1.txt renders intent guidance and neighbour briefs
[ ] negative test: teaching guidance projection contains no page-object ID
[ ] negative test: rendered lesson-approach prompt contains no page-object ID
```

The last check is the one that matters. The barrier is only real if it holds in
the string actually sent to the model, not just in the DTO.

---

## 8. Evidence requirement for Run 1

Add to the kickoff's §7 report requirements:

```
- the exact lesson-approach prompt as sent, including substituted identity
- the exact form-planner prompt as sent
```

When Run 1's last brief is read and found thin, the first question is whether
the prompt asked for concreteness or assumed it. Without the sent prompt in the
evidence package, that question cannot be answered and the fix becomes guesswork.

---

## 9. What is deliberately not here

**No `stance` object.** Rejected in favour of rendering existing spec prose.

**No `not_when` work for the remaining 21 intents.** Eleven have clauses.
Whether that is enough is a Run 1 finding, not a pre-condition. The four
lessons span four subjects and will exercise different clusters — that is
better evidence for which records to write next than any estimate.

**No per-section form fallback.** v1.1 §11.5 has it as an execution strategy if
whole-lesson form outputs prove too large. Do not build it pre-emptively. The
architecture does not change if it is needed later.

> HISTORICAL INPUT — NOT IMPLEMENTATION AUTHORITY

# BUILD GOAL — Overnight Phase 1

**Monorepo root:** `C:\Projects\lectio and textbook agent`
**Mode:** autonomous, unattended. No human available until morning.
**Scope:** phases 0–10. Nothing beyond phase 10.
**Goal of the night:** a monorepo where the intent and object selectors can be run against real skeleton slots from a command line — with no pipeline, no renderer, and no LLM spend until someone chooses to spend it.

---

## Rules for unattended work

You are working with nobody to ask. That changes how to fail.

1. **Never guess a decision.** If a phase is ambiguous, stop it, write the question into `BLOCKERS.md`, move to the next independent phase. Do not pick an interpretation and continue.
2. **Never delete a test to make the suite green.** A red test with a note is useful. A deleted test hides the thing we needed to learn.
3. **Commit per phase**, with the message given. Partial phases still commit — commit what works and describe the gap.
4. **Stay inside the listed files.** No adjacent refactors, no dependency bumps, no formatting sweeps, no "while I was in here".
5. **Phases are ordered.** Each may assume the previous landed. Dependency notes say what breaks if you skip.
6. **Do not run anything that costs money.** Phase 10 builds a harness; it does not run it.

Keep `PROGRESS.md` at the root. One line per phase:
`PHASE n — DONE | PARTIAL | BLOCKED — <one sentence>`

---

## Target structure

```
C:\Projects\lectio and textbook agent\
│
├── package.json                    pnpm workspace root
├── pnpm-workspace.yaml
├── .gitignore
├── .env.example
├── README.md                       what this is, how to run each side
├── PROGRESS.md                     ← written tonight
├── BLOCKERS.md                     ← written tonight
├── BUILD_GOAL.md                   this file
│
├── packages/
│   └── lectio-page/                from C:\Projects\lectio - Copy
│       ├── contracts/              intent + object catalogues, v1.1.0
│       │   ├── intent-catalogue.v1.json
│       │   ├── object-catalogue.v1.json
│       │   ├── lectio-document-v2.schema.json
│       │   └── base-print.css
│       ├── fixtures/
│       ├── src/lib/
│       │   ├── catalogue/          objects.ts, compatibility.ts
│       │   ├── contract/           document.ts, intents.ts, validation.ts
│       │   ├── render/             LectioDocumentView, BlockView, objects/
│       │   └── normalize/
│       └── scripts/                export-contracts, render-fixture-pdf
│
└── apps/
    └── textbook/                   clone of text-book-generator @ xplore
        ├── backend/
        │   ├── src/
        │   │   ├── planning/            unit, path, skeleton, bridge
        │   │   ├── resource_specs/      ← schema v2, candidates.py
        │   │   ├── contracts/           ← catalogues.py added
        │   │   ├── v3_blueprint/        ← PlannedBlock added
        │   │   ├── v3_execution/
        │   │   ├── v3_review/
        │   │   └── generation/
        │   │       └── runtime/         ← renamed from v3_studio
        │   ├── resources/
        │   │   ├── skeletons.yaml           ← candidate_intents
        │   │   ├── specs/*.yaml             ← vocabulary blocks
        │   │   ├── intent-selector-v1.txt   ← new
        │   │   └── object-selector-v1.txt   ← new
        │   ├── scripts/
        │   │   └── selector_dryrun.py       ← new, the morning payoff
        │   └── tests/
        └── frontend/
```

**Two git histories.** `packages/lectio-page` and `apps/textbook` each keep their own `.git`. Do not init a repo at the monorepo root this session, and do not convert either to a submodule. Each side pushes to its own remote as before. Root-level files stay untracked for now — record this in `BLOCKERS.md` as a morning decision.

---

## Phase 0 — Monorepo setup

**The root path contains spaces.** Quote every path in every script, npm script, and Python invocation. Prefer forward slashes in config files. If a tool breaks on the space, record it in `BLOCKERS.md` rather than renaming the folder.

**Steps**

1. Create the root folder.
2. **Copy** `C:\Projects\lectio - Copy` → `packages/lectio-page`. Copy, do not move — the original stays as a fallback. Preserve `.git`.
3. Clone `https://github.com/richiewaweru/text-book-generator` → `apps/textbook`, checkout `xplore`.
4. Confirm `packages/lectio-page/contracts/intent-catalogue.v1.json` reads `"catalogue_version": "1.1.0"`. If it reads `1.0.0`, the wrong copy was taken — `git pull` in that package before continuing.

**`pnpm-workspace.yaml`**

```yaml
packages:
  - 'packages/*'
```

Do **not** add `apps/textbook/frontend` to the workspace. That frontend depends on published `lectio@0.6.0` — the v1 renderer — and hoisting it risks pnpm resolving to the v2 package, which has no v1 components and would break the running product.

**Root `package.json`**

```json
{
  "name": "lectio-textbook-monorepo",
  "private": true,
  "scripts": {
    "lectio:test": "pnpm --filter lectio-page test",
    "lectio:check": "pnpm --filter lectio-page check",
    "lectio:pdf": "pnpm --filter lectio-page pdf:fixture",
    "lectio:contracts": "pnpm --filter lectio-page export-contracts"
  }
}
```

**Root `.gitignore`**

```
node_modules/
.venv/
__pycache__/
*.pyc
.env
out/
.svelte-kit/
dist/
.pytest_cache/
```

**Root `.env.example`**

```
# Where the Python backend reads the v2 catalogues.
# Relative to apps/textbook/backend, or absolute.
LECTIO_CATALOGUE_DIR=../../packages/lectio-page/contracts
```

**Python environment.** Create `apps/textbook/backend/.venv` and install per the repo's existing instructions (`uv sync`, `Makefile`, or `README.md`). Do not invent a new toolchain.

**Verify** — `pnpm install` at root succeeds; `pnpm lectio:test` green; `pytest` runs in `apps/textbook/backend`.

**If the clone fails** (auth, network): note it, finish phase 0 for `packages/lectio-page`, and stop. Phases 1–10 all need `apps/textbook`.

---

## Phase 1 — Delete the free-generation path

Free-form generation bypasses the unit path, the objective-ownership check, and the skeleton. It is also the last consumer of the 30-component palette prompt.

**Do not delete `generation/v3_studio/` as a directory.** It is the shared runtime. Thirteen files across the xplore path import `dtos.py`, `signal_map.py`, `generation_writer.py`, `router.py`, and `build_v3_shared_prefix()`. Deleting the directory removes all generation, all persistence, and the entire API.

**Check first.** `backend/src/v3_blueprint/shadow.py` imports `V3InputForm`. Confirm shadow evaluation does not run against the free-generation route. If it does, record it in `BLOCKERS.md` and **skip this phase entirely** — losing a shadow baseline costs more than keeping a dead route one more day.

**Delete exactly these:**

| File | What |
|---|---|
| `generation/v3_studio/router.py` | handlers for `POST /narrow`, `POST /propose-intent`, `POST /generate/start`, plus helpers used only by them |
| `generation/v3_studio/prompts.py` | `_planner_index_block()`. **Keep `build_v3_shared_prefix()`.** |
| `v3_blueprint/planning/structural_planner.py` | the `_planner_index_block` import and every use of `planner_block` |
| tests | any test exercising only the three deleted routes |

**Then confirm the vocabulary is dead on the planning side:**

```
grep -rn "get_planner_index\|_planner_index_block\|available_components" backend/src
```

Remaining hits should be in `contracts/lectio.py` only, which the v1 write path still needs. Any planning-layer file still reading the palette → `BLOCKERS.md`, do not delete.

**Verify** — `pytest` passes; the three routes are gone from OpenAPI.
**Commit** — `feat(generation): remove free-generation path and component palette`

---

## Phase 2 — Rename the runtime

Mechanical, and it gets harder every commit you delay it.

```
generation/v3_studio/   →  generation/runtime/
v3_studio_router        →  generation_router
V3GenerationWriter      →  GenerationWriter
```

Update imports across `backend/src` and `backend/tests`.

**Do not change route URLs.** `/api/v1/v3/...` stays exactly as is. The frontend depends on them; URL changes are not in scope.

**Verify** — `pytest` passes; `grep -rn "v3_studio" backend/src backend/tests` returns nothing.
**Commit** — `refactor(generation): rename v3_studio to runtime`

---

## Phase 3 — Catalogue bridge

The catalogues are JSON in `packages/lectio-page/contracts/`. Python has no way to read them. Everything downstream needs this, so it comes before the schema work.

New file: `backend/src/contracts/catalogues.py`

Mirror the pattern in `contracts/lectio.py` — `lru_cache`, env-var override, clear error when the directory is missing.

```python
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


def _catalogue_dir() -> Path:
    from_env = os.environ.get("LECTIO_CATALOGUE_DIR")
    if from_env:
        path = Path(from_env)
        if not path.exists():
            raise FileNotFoundError(
                f"LECTIO_CATALOGUE_DIR is set to '{from_env}' but does not exist."
            )
        return path

    # backend/src/contracts -> backend/src -> backend -> textbook -> apps -> root
    default = (
        Path(__file__).resolve().parents[4]
        / "packages" / "lectio-page" / "contracts"
    )
    if not default.exists():
        raise FileNotFoundError(
            f"Catalogue directory not found at '{default}'. Set LECTIO_CATALOGUE_DIR."
        )
    return default


@lru_cache(maxsize=1)
def load_intent_catalogue() -> dict[str, Any]:
    path = _catalogue_dir() / "intent-catalogue.v1.json"
    return json.loads(path.read_text(encoding="utf-8"))["intents"]


@lru_cache(maxsize=1)
def load_object_catalogue() -> dict[str, Any]:
    path = _catalogue_dir() / "object-catalogue.v1.json"
    return json.loads(path.read_text(encoding="utf-8"))["objects"]


def get_intent(intent_id: str) -> dict[str, Any] | None:
    return load_intent_catalogue().get(intent_id)


def get_object(object_id: str) -> dict[str, Any] | None:
    return load_object_catalogue().get(object_id)


def is_selectable(intent_id: str) -> bool:
    record = get_intent(intent_id)
    return bool(record) and record.get("selectable") is not False


def selectable_intents() -> list[str]:
    return [i for i in load_intent_catalogue() if is_selectable(i)]


def is_compatible(object_id: str, intent_id: str) -> bool:
    if object_id == "heading":
        return False
    record = get_intent(intent_id)
    return bool(record) and object_id in record.get("valid_objects", [])


def clear_cache() -> None:
    load_intent_catalogue.cache_clear()
    load_object_catalogue.cache_clear()
```

**Verify the `parents[4]` hop lands on the monorepo root.** Assert it in a test. If the repo nests differently than assumed, fix the index and note it.

**Verify** — tests: 32 intents load, 10 objects load, `answer-key` not selectable, `heading` compatible with nothing, `aside` capacity has `maxPerSection: 2`.
**Commit** — `feat(contracts): add v2 catalogue loader`

---

## Phase 4 — Resource spec schema v2

File: `backend/src/resource_specs/schema.py`

**Add:**

```python
class IntentVocabulary(BaseModel):
    model_config = ConfigDict(extra="ignore")
    core: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)
    excluded: dict[str, str] = Field(default_factory=dict)      # intent -> reason


class ObjectVocabulary(BaseModel):
    model_config = ConfigDict(extra="ignore")
    allowed: list[str] = Field(default_factory=list)
    excluded: dict[str, str] = Field(default_factory=dict)      # object -> reason


class VocabularySpec(BaseModel):
    model_config = ConfigDict(extra="ignore")
    intents: IntentVocabulary = Field(default_factory=IntentVocabulary)
    objects: ObjectVocabulary = Field(default_factory=ObjectVocabulary)
```

**`SectionSpec`** — add, do not remove. Unmigrated specs must still parse.

```python
    candidate_intents: list[str] = Field(default_factory=list)
    min_blocks: int = 1
    max_blocks: int = 3
```

**`ResourceSpec`** — add:

```python
    vocabulary: VocabularySpec = Field(default_factory=VocabularySpec)
    produces_answer_key: bool = False
```

**`SupportModification`** — add alongside existing fields:

```python
    preferred_objects: list[str] = Field(default_factory=list)
    ensures_block: dict | None = None      # {"intent": str, "object": str}
```

**Verify** — all seven existing specs load unchanged; `pytest` passes.
**Commit** — `feat(resource-specs): add v2 vocabulary and block fields`

---

## Phase 5 — `resolve_candidates`

New file: `backend/src/resource_specs/candidates.py`

Lives here, not in `planning/`, so tests can import it without pulling in the DB layer.

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from resource_specs.schema import ResourceSpec


class SlotCandidates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_id: str
    core: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)
    excluded: dict[str, str] = Field(default_factory=dict)
    unknown: list[str] = Field(default_factory=list)

    @property
    def available(self) -> list[str]:
        return [*self.core, *self.optional]

    @property
    def is_empty(self) -> bool:
        return not self.available


def resolve_candidates(slot, spec: ResourceSpec) -> SlotCandidates:
    """Intersect a skeleton slot's candidate intents with a resource spec's
    vocabulary. Pure: no I/O, no LLM, deterministic.

    Ordering follows the slot, not the spec. Skeleton order is the lesson arc
    and changes rarely; spec files are edited often. Slot ordering keeps runs
    reproducible.
    """
    candidates = list(getattr(slot, "candidate_intents", []) or [])
    vocab = spec.vocabulary.intents

    core = [i for i in candidates if i in vocab.core]
    optional = [i for i in candidates if i in vocab.optional]
    excluded = {i: vocab.excluded[i] for i in candidates if i in vocab.excluded}
    unknown = [
        i for i in candidates
        if i not in vocab.core
        and i not in vocab.optional
        and i not in vocab.excluded
    ]

    return SlotCandidates(
        slot_id=getattr(slot, "slot_id", getattr(slot, "role", "")),
        core=core,
        optional=optional,
        excluded=excluded,
        unknown=unknown,
    )
```

`unknown` exists so a slot intent the spec never mentions is visible rather than silently dropped. That is a config gap, and phase 8 reports it.

**Verify** — unit tests: normal intersection, empty result, exclusion reasons carried, ordering follows slot, unknown populated.
**Commit** — `feat(resource-specs): add resolve_candidates`

---

## Phase 6 — Data: skeletons and two specs

### 6a. `backend/resources/skeletons.yaml`

Add `candidate_intents` to each of the 13 slots. **Keep `preferred:` and `allowed:`** — the v1 path still reads them; they die with v1.

```yaml
orient:        candidate_intents: [orient, activate-prior-knowledge]
recall:        candidate_intents: [activate-prior-knowledge, connect-back, check-understanding]
model:         candidate_intents: [demonstrate, derive, sequence, model-thinking]
explain:       candidate_intents: [explain, explain-cause, define, trace-flow, show-structure]
contrast:      candidate_intents: [compare, classify, define]
confront:      candidate_intents: [diagnose-misconception, warn, compare]
organise:      candidate_intents: [show-structure, classify, name-parts, summarise]
criteria:      candidate_intents: [define, evaluate, compare]
guided:        candidate_intents: [practise-guided, apply]
independent:   candidate_intents: [practise-independent, apply]
apply:         candidate_intents: [transfer, apply, interpret]
check:         candidate_intents: [check-understanding, diagnose-misconception]
close:         candidate_intents: [summarise, connect-forward, reflect]
```

Bump `version: 1` → `version: 2`.

`v3_blueprint/skeletons.py` must expose `candidate_intents` on the slot model. Add the field; leave `allowed_components` in place.

### 6b. `backend/resources/specs/lesson.yaml`

```yaml
produces_answer_key: true

vocabulary:
  intents:
    core:
      - orient
      - activate-prior-knowledge
      - define
      - explain
      - explain-cause
      - demonstrate
      - practise-guided
      - practise-independent
      - check-understanding
      - diagnose-misconception
      - warn
      - emphasise
      - summarise
      - connect-forward
    optional:
      - name-parts
      - show-structure
      - sequence
      - compare
      - classify
      - trace-flow
      - interpret
      - derive
      - apply
      - connect-back
      - memory-aid
    excluded:
      investigate: "A lesson is not a practical. Use an investigation resource."
      evaluate: "Judgement work needs its own resource and more page space."
      transfer: "Far transfer belongs in consolidation, not first exposure."
      model-thinking: "Reserved until the model-thinking prompt is proven."
      reflect: "Reflection belongs at the close of a unit, not every lesson."
      state-goal: "The objective already appears in the section header."
  objects:
    allowed: [heading, prose, list, table, figure, aside, worked-example, questions, choices, answer-key]
    excluded: {}
```

Then add `candidate_intents`, `min_blocks`, `max_blocks` to each entry under `sections.required` / `sections.optional`, matching the slot names in 6a.

### 6c. `backend/resources/specs/worksheet.yaml`

```yaml
produces_answer_key: true

vocabulary:
  intents:
    core: [practise-guided, practise-independent, apply, warn]
    optional: [connect-back, memory-aid, transfer]
    excluded:
      demonstrate: "A worksheet rehearses a method; it does not teach it."
      model-thinking: "Expert reasoning belongs in the lesson."
      derive: "Justification belongs in the lesson."
      explain: "A worksheet that explains is a lesson with questions."
      explain-cause: "A worksheet that explains is a lesson with questions."
      define: "Definitions belong in the lesson or a revision sheet."
      orient: "A worksheet follows teaching; it does not open it."
  objects:
    allowed: [heading, prose, list, table, figure, questions, choices, worked-example]
    excluded:
      aside: "Margin notes are teaching scaffolding; worksheets carry instructions in the flow."

supports:
  worked_examples:
    intent_note: >
      This learner group needs the method held open while they work.
      Prefer partially-completed examples over bare prompts.
    ensures_block:
      intent: practise-guided
      object: worked-example
    preferred_objects: [worked-example]
```

**The worksheet allows the `worked-example` object but excludes the `demonstrate` intent.** Deliberate. `worked-example` + `demonstrate` is re-teaching; `worked-example` + `practise-guided` is scaffolding. Same form, different job. Do not "fix" this.

**Do not migrate the other five specs.** They stay v1; every new field has a default, so the loader tolerates both.

**Verify** — all seven specs load; `resolve_candidates` non-empty for every lesson slot.
**Commit** — `feat(specs): add v2 vocabulary to skeletons, lesson, and worksheet`

---

## Phase 7 — Prompt files

Copy the two companion artifacts verbatim into:

```
backend/resources/intent-selector-v1.txt
backend/resources/object-selector-v1.txt
```

**Do not edit, condense, reformat, or improve the wording.** Every clause is load-bearing and the phrasing has been argued over. If something reads oddly, note it in `BLOCKERS.md` — do not change it.

**Verify** — files present, byte-identical to the supplied text.
**Commit** — `feat(prompts): add intent and object selector prompts`

---

## Phase 8 — Coverage tests

New file: `backend/tests/resource_specs/test_spec_skeleton_pairs.py`

Three tests off one cross-product.

**Test 1 — no empty candidate set**

```python
def test_every_slot_has_available_intents():
    errors = []
    catalog = load_skeleton_catalog()
    spec = get_spec("lesson")
    for skeleton in catalog.skeletons:
        for slot_id in skeleton.slots:
            c = resolve_candidates(catalog.slot(slot_id), spec)
            if c.is_empty:
                errors.append(
                    f"{spec.id} x {skeleton.id}: slot '{slot_id}' has no available intent "
                    f"(excluded: {sorted(c.excluded)}, unknown: {c.unknown})"
                )
    assert not errors, "\n".join(errors)
```

**Test 2 — no unknown intents**

A `candidate_intent` the spec neither allows nor excludes is a config gap. Report all of them in one assertion message.

**Test 3 — every co-occurring pair has a `not_when` clause**

The one that matters. It replaces guesswork about which catalogue records to write with a computed answer.

```python
def test_cooccurring_intents_have_not_when():
    pairs = set()
    catalog = load_skeleton_catalog()
    spec = get_spec("lesson")
    for skeleton in catalog.skeletons:
        for slot_id in skeleton.slots:
            c = resolve_candidates(catalog.slot(slot_id), spec)
            for a, b in combinations(sorted(c.available), 2):
                pairs.add((a, b))

    catalogue = load_intent_catalogue()
    missing = [
        (a, b) for a, b in sorted(pairs)
        if b not in catalogue.get(a, {}).get("not_when", {})
        and a not in catalogue.get(b, {}).get("not_when", {})
    ]
    assert not missing, (
        "Intent pairs that can co-occur but have no not_when clause:\n"
        + "\n".join(f"  {a} / {b}" for a, b in missing)
    )
```

**Test 3 will fail on first run. That is expected and it is the point.** Eleven intents carry `not_when`; the cross-product will surface more pairs.

Do **not** write the missing clauses. Instead:

1. Run the test.
2. Write the full failure output into `BLOCKERS.md` under `## Missing not_when pairs`.
3. Mark it `@pytest.mark.xfail(reason="v1.1 catalogue covers 11 intents; pairs pending")`.
4. Move on.

The list is the deliverable. It says exactly which catalogue records to write next, computed rather than estimated.

**Verify** — tests 1 and 2 green or their failures recorded; test 3 xfail with the pair list in `BLOCKERS.md`.
**Commit** — `test(resource-specs): add spec x skeleton coverage tests`

---

## Phase 9 — Planning models (additive)

File: `backend/src/v3_blueprint/planning/models.py`

**Add. Do not remove `ComponentSlot` or `SectionPlan.components`** — the v1 path still writes them, and this phase does not replace the pipeline.

```python
class PlannedBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: int = Field(description="Order within the section. 0-based.")
    intent: str = Field(description="IntentId from the catalogue.")
    object: str = Field(description="PageObject from the catalogue.")
    brief: str = Field(
        description="What this block must contain, for this concept. "
        "Specific enough that it would not fit another lesson.",
    )
    evidence: str | None = Field(
        default=None,
        description="The input that decided the intent. Audit trail.",
    )
    layout_placement: Literal["main", "margin"] = "main"
```

On `SectionPlan`, add alongside `components`:

```python
    blocks: list[PlannedBlock] = Field(default_factory=list)
```

**Add validation helpers** in `v3_blueprint/planning/validators.py`, as new functions — do not touch the existing ones:

```python
def validate_planned_blocks(section, spec) -> list[str]:
    """Structural checks only. No pedagogy.
      - intent exists in the catalogue and is selectable
      - object exists in the catalogue
      - is_compatible(object, intent)
      - object is in spec.vocabulary.objects.allowed
      - positions contiguous from 0, no duplicates
      - block count within min_blocks / max_blocks
      - no heading object (headings come from section.title)
      - margin placement only for aside
    """
```

**Verify** — unit tests for each rule; existing tests unaffected.
**Commit** — `feat(planning): add PlannedBlock model and structural validation`

---

## Phase 10 — Dry-run harness

**This is what makes tomorrow productive.** It runs the selector test without the pipeline, the renderer, or a database.

New file: `backend/scripts/selector_dryrun.py`

```
Usage:
  python scripts/selector_dryrun.py \
      --knowledge-type conceptual \
      --lesson-mode first_exposure \
      --objective "explain why plants cannot make food in darkness" \
      --misconception "plants take food from the soil" \
      --spec lesson \
      [--slot explain]   restrict to one slot
      [--dry]            print the prompts, make no LLM call
      [--json out.json]  write the full result
```

**What it does**

```
1. load skeleton for knowledge_type x lesson_mode
2. for each slot:
     resolve_candidates(slot, spec)
     build the Step 1 prompt   ← intent-selector-v1.txt + rendered context
     if --dry: print it, continue
     else:     call the model, parse blocks[]
     for each block:
        available = intent.valid_objects ∩ spec.vocabulary.objects.allowed
        build the Step 2 prompt  ← object-selector-v1.txt + brief
        call, parse
3. print a table:
     SLOT | INTENT | EVIDENCE | OBJECT | REASON | BRIEF
```

**Prompt rendering rules — implement exactly, they are the design:**

- Step 1 receives **only** the resolved candidates. Never the full 32. Never a "do not use these" list of non-candidates.
- Step 1 receives **no object information at all.** Not names, not schemas, not counts. That barrier is the entire reason there are two steps.
- Render `not_when` under the heading `do_not_choose_when`, to match the prompt file's wording.
- `not_when` clauses whose key is **not** in the candidate set: keep the clause text, drop the intent name. Naming an unpickable intent is noise and invites the model to pick it.

  ```
  DO NOT CHOOSE explain WHEN:
    - the objective asks WHY and a mechanism links cause to result
                                             -> choose explain-cause
    - a specific representation is on the page and must be read
  ```

  The first names an in-scope alternative. The second is still a valid rejection test with the out-of-scope name removed.
- Excluded intents are passed as `excluded_intents` with reasons, for the model's information only. They are not selectable.
- Step 2 receives the brief, the intent, and the intersected object list with `earns_its_place_when`, `reject_when`, and `capacity`.

**Model config.** Use the existing `run_json_agent` / `get_v3_model` machinery rather than a new LLM client. Register two nodes in `v3_execution/config/models.py`: `v2_intent_selector`, `v2_object_selector`. Point both at the model the current `component_selector` uses.

**Do not run it tonight.** Build it, unit-test the prompt rendering against a stub model, verify `--dry` prints sensible prompts. No paid calls.

**Verify** — `--dry` prints both prompt types for a real skeleton; rendering tests pass with a stubbed model.
**Commit** — `feat(scripts): add selector dry-run harness`

---

## Stop here

Do not begin: writer prompt changes, `section_builder`, `block_ready` events, projections, frontend work, the v2 renderer, wiring the selectors into `bridge.py`, or the remaining 21 catalogue records.

---

## Record, do not solve

Put these in `BLOCKERS.md` as open questions for the morning. Do not act on them.

1. **Root-level git.** Two histories, no root repo. Is that the long-term shape, or does the root eventually get its own repo with the two as subtrees?
2. **When does the textbook frontend join the workspace?** Not tonight — it needs `lectio@0.6.0`. It moves when the v2 renderer can serve both.
3. **`contracts/lectio.py` still lives.** The v1 write path needs it. It dies when v1 does. Note anything that touches it.
4. **Playwright on Windows.** `pnpm lectio:pdf` needs a Chromium install. If `postinstall` fails on the space in the path, record the exact error.
5. **Docker.** `docker-compose.yml` in `apps/textbook` still assumes the old repo root. Untouched tonight.
6. **`criteria` slot.** `candidate_intents: [define, evaluate, compare]`, but `lesson.yaml` excludes `evaluate` — so it resolves to two. Test 1 confirms it is non-empty. Flag whether two is enough for a real decision.

---

## Morning report

`BLOCKERS.md` must contain, at minimum:

1. **The missing `not_when` pair list from phase 8** — the highest-value output of the night
2. Whether shadow evaluation blocked phase 1
3. Any slot with an empty candidate set, or any `unknown` intents
4. The six items above
5. Anything you chose not to guess at

---

## Acceptance

```
SETUP
[ ] monorepo at the given path; both projects present
[ ] catalogues read catalogue_version 1.1.0
[ ] pnpm install and pnpm lectio:test green
[ ] pytest runs in apps/textbook/backend

CLEANUP
[ ] three free-generation routes gone; _planner_index_block gone
[ ] build_v3_shared_prefix still present and used
[ ] no "v3_studio" string in backend/src or backend/tests
[ ] route URLs unchanged (/api/v1/v3/...)

NEW SURFACE
[ ] contracts/catalogues.py loads 32 intents and 10 objects
[ ] answer-key not selectable; heading compatible with nothing
[ ] VocabularySpec, candidate_intents, min_blocks/max_blocks on the schema
[ ] resolve_candidates pure, unit tested, in resource_specs/
[ ] 13 slots have candidate_intents; skeletons.yaml version 2
[ ] lesson.yaml and worksheet.yaml have vocabulary blocks
[ ] other five specs still load unchanged
[ ] PlannedBlock added; SectionPlan.components untouched
[ ] validate_planned_blocks unit tested

TESTS AND TOOLING
[ ] tests 1 and 2 green or recorded
[ ] test 3 xfail with the pair list in BLOCKERS.md
[ ] both prompt files byte-identical to the supplied text
[ ] selector_dryrun.py --dry prints both prompts for a real skeleton
[ ] no LLM calls were made

REPORT
[ ] PROGRESS.md, one line per phase
[ ] BLOCKERS.md with all five required sections
```

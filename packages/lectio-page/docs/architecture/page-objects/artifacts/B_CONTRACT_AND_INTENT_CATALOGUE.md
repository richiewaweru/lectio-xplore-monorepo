# B. Contract — Object Catalogue and Intent Vocabulary

## Executive decision

The v2 contract contains ten stable physical document objects and 32 pedagogical intents.

The object catalogue is intentionally small because objects own page behavior. The intent catalogue is intentionally richer because it must absorb the pedagogical roles, cognitive jobs, planner guidance, and QC meaning previously carried by 33 component names.

A thin intent vocabulary would be a regression. The acceptance threshold for the initial catalogue is at least 28 useful intents spanning orientation, explanation, representation, procedure, practice, assessment, misconception handling, consolidation, reflection, inquiry, and teacher guidance.

## 1. Canonical root

```ts
export interface LectioDocument {
  document_version: 2;
  contract_version: string;
  id: string;
  title: string;
  language: string;
  subject?: string;
  audience?: Audience;
  metadata: DocumentMetadata;
  sections: LectioSection[];
  answer_key?: AnswerKeyBlock;
}

export interface LectioSection {
  id: string;
  title: string;
  blocks: DocumentBlock[];
}
```

The array order is canonical. No renderer, builder, merge function, or serializer may infer a different order.

## 2. Shared block shape

```ts
interface BlockBase {
  id: string;
  object: PageObject;
  intent: IntentId;
  position: number;
  role?: string;
  source?: BlockSource;
  layout?: LayoutHint;
}
```

`position` is carried during generation and normalized to array order on commit. Stable IDs are mandatory.

## 3. Inline content

The stored contract uses restrained typed inline nodes:

```ts
type InlineNode =
  | { type: 'text'; value: string }
  | { type: 'strong'; children: InlineNode[] }
  | { type: 'emphasis'; children: InlineNode[] }
  | { type: 'small-caps'; children: InlineNode[] }
  | { type: 'term'; value: string; definition?: string }
  | { type: 'math'; latex: string }
  | { type: 'reference'; target_id: string; label: string };
```

Raw HTML is forbidden. Markdown may be accepted at a writer boundary but must be normalized before persistence.

## 4. Object catalogue

See `contracts/lectio-document-v2.schema.json` for machine-readable schemas.


### `heading`

**Holds:** Heading text, hierarchy level, optional numbering.

**Content schema:** `{"level": "1|2|3", "text": "string", "number": "string|null"}`

**Placement:** main, spanning

**Fragmentation:** Must be bound with the first following block in one break-inside:avoid wrapper. Never render alone.

**Emphasis:** Type size, weight, rule, and spacing only. No box.


### `prose`

**Holds:** Paragraphs and restrained inline nodes.

**Content schema:** `{"paragraphs": "RichParagraph[]"}`

**Placement:** main

**Fragmentation:** Splits freely with widows/orphans. Paragraphs may split.

**Emphasis:** Inline weight, italic, small caps, and whitespace. No background or border.


### `list`

**Holds:** Ordered or unordered items with optional lead-in.

**Content schema:** `{"style": "ordered|unordered|steps|glossary", "lead_in": "RichText|null", "items": "ListItem[]"}`

**Placement:** main, margin

**Fragmentation:** List may split between items; individual item avoids splitting when practical.

**Emphasis:** Markers, hanging indent, weight, and spacing. No box.


### `table`

**Holds:** Columns, rows, header, caption, and semantic presentation hint.

**Content schema:** `{"columns": "TableColumn[]", "rows": "TableRow[]", "caption": "string|null", "presentation": "standard|comparison|timeline"}`

**Placement:** main, spanning

**Fragmentation:** May split across pages. thead repeats. Rows avoid splitting.

**Emphasis:** Rules, alignment, weight, and sparse header tint only when photocopy-safe. No enclosing box.


### `figure`

**Holds:** Image or SVG asset, caption, alt text, width hint.

**Content schema:** `{"asset": "FigureAsset", "caption": "string|null", "alt_text": "string", "width": "main|span"}`

**Placement:** main, spanning

**Fragmentation:** Figure and caption are atomic. May move to next page.

**Emphasis:** Scale, whitespace, caption typography, and optional hairline around the plate only—not a card.


### `aside`

**Holds:** Short set-apart note with optional student-facing label.

**Content schema:** `{"label": "string|null", "body": "RichText"}`

**Placement:** margin, main

**Fragmentation:** Atomic. Margin placement uses float, clear:right, and negative margin. Move cleanly if it does not fit.

**Emphasis:** The only object allowed a border or background. Default is a single vertical rule with restrained label.


### `worked-example`

**Holds:** Problem/setup, ordered reasoning steps, final answer, optional checks.

**Content schema:** `{"title": "string|null", "problem": "RichText", "steps": "WorkedStep[]", "answer": "RichText", "check": "RichText|null"}`

**Placement:** main, spanning

**Fragmentation:** May split between steps. A step avoids internal split where practical. Final step and answer stay together.

**Emphasis:** Numbered steps, hanging labels, indentation, and rules. No enclosing box.


### `questions`

**Holds:** Open prompts, marks, response guidance, answer-space specification.

**Content schema:** `{"items": "QuestionItem[]", "instructions": "RichText|null"}`

**Placement:** main, spanning

**Fragmentation:** Split between questions, never inside a question. Prompt stays with minimum answer space.

**Emphasis:** Hanging numbers, marks aligned to edge, ruled answer space. No cards.


### `choices`

**Holds:** Stem, lettered options, optional marks.

**Content schema:** `{"stem": "RichText", "options": "ChoiceOption[]", "marks": "number|null"}`

**Placement:** main

**Fragmentation:** Atomic when it fits; otherwise keep stem with at least two options and split only between options.

**Emphasis:** Letters A/B/C/D, hanging indent, whitespace. Never radio controls.


### `answer-key`

**Holds:** Question references, expected answers, alternatives, working, rubric and misconceptions.

**Content schema:** `{"groups": "AnswerGroup[]"}`

**Placement:** main, spanning

**Fragmentation:** Split between entries. Entry keeps question reference with first answer line.

**Emphasis:** Heading hierarchy, compact typography, rules. No card.


## 5. Intent catalogue

The table below is normative. Machine-readable form is in the repo-root `contracts/intent-catalogue.v1.json` (not duplicated under this pack).

| Intent | Teacher label | Pedagogical role | Cognitive job | Valid objects |
|---|---|---|---|---|
| `orient` | Orient | Open attention and establish a reason to learn | activate curiosity and situational framing | prose, figure, choices |
| `activate-prior-knowledge` | Recall what you know | Surface prerequisite knowledge | retrieve relevant prior knowledge | prose, list, questions, choices |
| `state-goal` | Learning goal | Clarify the expected learning outcome | metacognitive goal setting | prose, list |
| `define` | Define | Establish precise meaning | concept formation and vocabulary encoding | prose, table, aside |
| `name-parts` | Name the parts | Identify constituent elements | decomposition and labeling | list, table, figure |
| `classify` | Classify | Organize examples into categories | categorical reasoning | list, table, questions, choices |
| `compare` | Compare | Expose similarities and differences | relational comparison | table, prose, questions |
| `sequence` | Put in order | Represent an ordered process | temporal and procedural ordering | list, table, figure, questions |
| `explain` | Explain | Build a coherent mental model | causal and conceptual understanding | prose, figure, table |
| `explain-cause` | Explain cause and effect | Connect causes, mechanisms, and outcomes | causal reasoning | prose, figure, table, questions |
| `trace-flow` | Trace the flow | Follow matter, energy, information, or value | systems tracing | figure, list, table, prose |
| `show-structure` | Show the structure | Reveal spatial or hierarchical organization | structural visualization | figure, table, list |
| `demonstrate` | Worked demonstration | Model a complete method | procedural modeling | worked-example, figure |
| `model-thinking` | Think aloud | Expose expert decision making | metacognitive strategy modeling | worked-example, prose |
| `derive` | Derive | Build a result from prior statements | deductive reasoning | worked-example, prose, table |
| `interpret` | Interpret | Translate representation into meaning | representational fluency | prose, figure, table, questions |
| `apply` | Apply | Use knowledge in a familiar situation | near transfer | questions, worked-example, table |
| `transfer` | Transfer | Use knowledge in a changed context | farther transfer and abstraction | questions, worked-example |
| `practise-guided` | Guided practice | Rehearse with structured support | scaffolded retrieval and execution | questions, worked-example |
| `practise-independent` | Independent practice | Rehearse without scaffolding | independent retrieval and execution | questions, choices |
| `check-understanding` | Quick check | Detect immediate misunderstanding | formative assessment | questions, choices |
| `diagnose-misconception` | Diagnose misconception | Distinguish a known wrong model from the target model | misconception diagnosis | choices, questions, aside |
| `warn` | Watch out | Prevent a predictable error | error avoidance | aside, prose |
| `emphasise` | Key idea | Mark a high-value statement | selective attention and encoding | aside, prose |
| `memory-aid` | Memory aid | Support recall with a compact cue | mnemonic encoding | aside, list |
| `summarise` | Summarise | Compress the lesson into essential relationships | schema consolidation | list, prose, table |
| `connect-forward` | What comes next | Bridge current learning to the next idea | curricular coherence | prose, list |
| `connect-back` | Use what came before | Make prerequisite dependence explicit | knowledge integration | prose, list, questions |
| `reflect` | Reflect | Prompt learners to examine their understanding | metacognitive monitoring | questions, prose |
| `investigate` | Investigate | Structure an inquiry or practical | scientific and empirical reasoning | questions, list, table, figure |
| `evaluate` | Evaluate | Judge a claim, method, or evidence | critical evaluation | questions, table, prose |
| `answer-key` | Teacher guidance | Provide checking and marking guidance | assessment interpretation | answer-key |

## 6. Intent rules

1. Intent cannot select a renderer.
2. Intent may control teacher-facing naming, prompt guidance, QC, and restrained emphasis.
3. Intent may not create a new box style.
4. Object-intent compatibility is validated.
5. New intents require:
   - unique pedagogical role;
   - unique cognitive job or generation guidance;
   - at least one valid object;
   - no new document structure.
6. If an intent requires different fragmentation, it is evidence for a new object—not a special intent renderer.
7. Student-visible labels are optional and rare. Internal intent IDs never print.

## 7. Exported JSON shape

```json
{
  "catalogue_version": "1.0.0",
  "objects": {
    "prose": {
      "schema_ref": "#/$defs/prose",
      "placements": ["main"],
      "fragmentation": {
        "split": "free",
        "widows": 3,
        "orphans": 3
      }
    }
  },
  "intents": {
    "explain": {
      "teacher_label": "Explain",
      "pedagogical_role": "Build a coherent mental model",
      "cognitive_job": "causal and conceptual understanding",
      "valid_objects": ["prose", "figure", "table"],
      "generation_guidance": "Explain why or how..."
    }
  }
}
```

## 8. Differentiation boundary

Differentiation lives above object and intent.

```text
learner profile
    ↓
lesson shape and support strategy
    ↓
object sequence + intent sequence + content constraints
    ↓
generated document
```

Support/core/extension may alter:

- object count;
- sequence;
- prose density;
- number of figures;
- scaffold level;
- question type;
- answer-space allocation;
- inclusion of memory aids;
- worked-example granularity.

Do not create intents such as `support`, `core`, or `extension`.

## 9. Answer-key policy

Answer keys are mixed derived and authored content.

- Choices and constrained items may derive exact answers.
- Open responses require authored acceptable answers.
- Evaluation tasks require criteria or rubric.
- Worked solutions may require full reasoning.
- Reflection may have guidance rather than one correct answer.

## 10. Contract invariants

- Blocks are ordered and repeatable.
- Duplicate object types are valid.
- IDs are unique within a document.
- `position` and array order cannot disagree after normalization.
- Every intent is compatible with the block object.
- Figure alt text is mandatory.
- Heading cannot be the final block in a section.
- Aside body must be short enough for atomic placement; initial limit 120 words.
- Choices contain at least two options.
- Question IDs referenced by answer key must exist.
- Document root carries a valid BCP-47 language code so hyphenation can work.

**DOCUMENT VERSION:** 1.0  
**DEPENDS ON:** JSON Schema and intent catalogue in `/contracts`

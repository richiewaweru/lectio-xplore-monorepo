# 36 — Lesson Presentation Revamp: Learn and Print That Look Designed

Status: PROPOSED DIRECTION (rev 1, 2026-10-05) — work order for the coding agent (ChatGPT / Codex), to land today
Repo: `richiewaweru/lectio-xplore-monorepo`, app `apps/textbook-agent`
Related: `35_MEDIA_TRUTH_AND_EXECUTION_FIX.md` (owns every figure decision; this doc only frames and captions figures), `34_DEMO_SLICE_AMENDMENT.md`
Visual reference: the design canvas "Lesson presentation revamp" (Learn screen, three A4 worksheet pages, one teacher answer page). The owner attaches screenshots of it to each task. Where a screenshot and this document disagree, this document wins.

Caveat for the agent: this document was written from two screen recordings, one exported lesson JSON and an earlier codebase summary, not from reading the repo. File paths marked "locate" must be found before editing. Section 9 lists what to verify first.

## 0. Goal

A generated lesson must read as a designed lesson, not as generated blocks poured into a renderer. Concretely:

1. **Nothing the writer produced is lost on the way to the screen or the page.** Paragraph breaks, list numbering, headings, emphasis, subscripts and equations all arrive.
2. **Every kind of block has one recognisable look**, the same idea in Learn and in Print, so a learner always knows whether they are reading, being told the key point, being warned about a mistake, or being asked to do something.
3. **The writer shapes content, not just writes it**: short paragraphs, subheadings where a section changes job, bold key terms, real lists, one key idea per explaining section.
4. **Learn and Print render the same shared document word for word.** Neither path rewrites, trims or re-authors content.

**Not a goal:** new pipeline architecture, figure decisions (doc 35), content quality gates, the Print editor's edit mode, class or student runtime.

Principle carried over from the SharedDocument work: the shared document owns semantic presentation; Learn owns screen presentation; Print owns page presentation.

## 1. What is wrong today (observed, with evidence)

Lesson used throughout: "How Plants Get the Energy to Grow" (`learn-out-2e28762bdccd46ed`).

| # | Observed | Where | Cause |
|---|---|---|---|
| 1 | Three paragraphs separated by `\n\n` in one node render as one block | Learn and Print | Renderers do not split on blank lines |
| 2 | List with `ordered: true` renders with no numbers | Learn and Print | Ordered flag ignored / list style reset |
| 3 | Section titles ("Two Pots, One Difference") never appear in the Learn body; only tabs exist | Learn | Titles only feed the tab tooltip |
| 4 | Tabs show the section id ("Orient", "Explain") | Learn, `OrderedDocumentList.svelte` | Visible text bound to `section.id` |
| 5 | "DOCUMENT · V2" and "10 nodes" shown to the learner | Learn | Debug metadata in the learner view |
| 6 | Body text about 13px on lines about 150 characters long, words hyphenated mid-line | Learn | No reading column; flat 16px grid gap in `DocumentCanvas` |
| 7 | Callout is smaller than body text and about 130 words long | Learn | Callout style; no length guidance |
| 8 | Callout squeezed into a narrow side column with a half-empty page | Print | Print callout layout |
| 9 | Task prompt repeats the whole scenario from the paragraph above it | Both | Task prompt authored as self-contained |
| 10 | Feedback is "Correct." / "Not yet — try again." A prediction task is marked right or wrong | Learn | Generic feedback; no task role |
| 11 | Answer key reads "Choice-1. B" | Print | Label derived from interaction type |
| 12 | A two-page worksheet opens with a contents list | Print | Always-on table of contents |
| 13 | No bold, subscript or formula anywhere; every `text` field is a plain string | Shared document | No inline formatting in the model |
| 14 | The fifth "step" of a numbered list is a summary, not a step | Writer | No list discipline |
| 15 | No figure in a lesson built on a two-pot comparison | Plan | Doc 35 territory; not fixed here |

## 2. The settled design

### 2.1 Block vocabulary

One table, both renderers. "Exists" means the node kind is already in `SharedLessonDocument`.

| Block | Status | Meaning to the learner | Learn look | Print look |
|---|---|---|---|---|
| Section header | exists (section title) | A new part starts | 2px ink rule above, "PART 2 OF 4" eyebrow, 30px bold title | 2px rule, filled square number badge, 21px bold title |
| Subheading (h3) | exists | The section changes job | 21px bold, extra space above | 16px bold, extra space above |
| Paragraph | exists | Reading | On the page, never in a card. 18px, line-height 1.6 | 16px (12pt), line-height 1.4 |
| Unordered list | exists | Parallel points | Real bullets, 8px between items | Real bullets |
| Ordered list | exists | Steps in order | Filled green numeral circles, 14px between steps | Outlined numeral circles |
| Key idea | **new callout variant** | The one sentence to remember | Green tint block, "KEY IDEA" label, 22px bold sentence | Green tint plus 1px border, 18px bold |
| Note | **new callout variant** | Worth noticing | Sand tint block with label | Light grey block with label |
| Misconception | **new callout variant, structured** | A belief people hold, and why it fails | White card, sand header "COMMON BELIEF n", three rows: The belief (italic, quoted) / The evidence / So | Bordered box, grey header, same three rows |
| Figure | exists | Look at this | White bordered frame, caption below starting "Figure n." | 1px bordered frame, 13px caption |
| Table | exists | Compare | White bordered frame, header row with 2px rule, scrolls sideways on a phone | Full grid, 1px rules, grey header row |
| Equation | **new** | The process in one line | Bordered box, terms as chips, arrow with the condition written above it | Same, black outlines |
| Quote | **new** | Someone's claim | Sand block, serif 23px | Grey block, serif 18px |
| Compare | **new** | Two or three options side by side | Sand cards in a grid that stacks on a phone | Two bordered boxes side by side |
| Task | exists (TaskAnchor) | Your turn | The only block with a 2px ink border and a dark header strip: "YOUR TURN · QUESTION n" left, mode right | 2px border, black header strip "QUESTION n · PREDICT/CHECK", tick circles, answer lines |

Two rules the renderers enforce by construction:

- **Prose never sits in a card.** Cards and tinted blocks are reserved for the non-paragraph kinds above.
- **The dark header strip appears only on tasks.** It is the signal for "you do something now".

### 2.2 Inline formatting (the main model change)

Keep every text field a string. Add a small inline markup that both renderers parse. No schema migration, old documents render unchanged.

| Markup | Meaning | Example |
|---|---|---|
| `**text**` | Key term / strong | `absorb **light energy**` |
| `*text*` | Emphasis | `*not* from the soil` |
| `~text~` | Subscript | `CO~2~` |
| `^text^` | Superscript | `m^2^` |
| blank line (`\n\n`) | Paragraph break inside a paragraph node | already produced today |

Rules:

- Applies to every learner-facing string: paragraph text, list items, callout parts, table cells, captions, quote text, compare bodies, equation terms, task prompts, options and feedback.
- No nesting beyond `**` containing `~`/`^`. No links, headings, lists or HTML inside strings.
- Parsing is total: unmatched or unknown markup is shown as literal characters. The parser never raises and never drops text.
- HTML in strings is always escaped.
- One parser per side, each with the same test vectors (section 2.6 fixture): TypeScript for Learn, Python for Print. Do not add a markdown library; the grammar is four tokens.
- Writers use this markup instead of Unicode subscript characters. Plain Unicode symbols such as `→`, `×`, `°` and `½` are allowed as they are.
- Content hashing is unchanged; markup is part of the text.

### 2.3 New and changed nodes

All additions are optional fields or new kinds with safe defaults. Stored documents must load and render exactly as before, and their content hashes must not change.

```text
Callout (changed)
  variant: "key_idea" | "note" | "misconception" | null     # null = today's behaviour
  title:   str | null
  body:    str | null                                       # key_idea, note
  belief:      str | null                                   # misconception only
  evidence:    str | null
  conclusion:  str | null
  aside:       str | null                                   # optional short follow-up shown under the box

Equation (new)
  label:      str | null            # e.g. "In one line"
  inputs:     [str]                 # 1..4 terms
  condition:  str | null            # written above the arrow
  outputs:    [str]                 # 1..3 terms

Quote (new)
  text:        str
  attribution: str | null           # e.g. "A student says"

Compare (new)
  items: [ { label: str | null, title: str, body: str } ]   # 2..3 items

Task (changed; exact home on TaskAnchor or shared_task to be confirmed, section 9)
  role:           "predict" | "practice" | "check"
  display_prompt: str               # the question only
  feedback:       { correct: str, incorrect: str } | { saved: str }   # predict uses saved
  option_notes:   { option_id: str } | null                 # teacher-facing reason an option is wrong
```

A misconception missing any of its three parts falls back to rendering `body` as a note. A renderer that meets an unknown node kind renders its text fields as paragraphs and logs once; it never throws and never shows a placeholder.

### 2.4 Shaping rules for the composer and the writer

These go into the composer and writer prompts as instructions with the stated targets.

1. A paragraph holds one idea, three or four sentences. Start a new paragraph (blank line) when the idea changes.
2. Add a subheading when a section changes job (setting up, explaining, summarising what a part is for). A section of more than about 120 words of prose normally has at least one.
3. Bold a key term once, where it is introduced or defined. About two to five per section. Never bold whole sentences.
4. An ordered list is only for steps in order; an unordered list only for parallel items. Every item is the same kind of thing. A closing summary is a note, not a list item.
5. Each explaining section opens with exactly one key idea: one sentence stating the point.
6. A misconception is always written as belief / evidence / conclusion. The belief is in the believer's words.
7. Use a table when two or more things are compared on the same attributes. Use an equation when a process has inputs and an output. Use compare for two or three rival options. Use a quote for a claim someone makes.
8. The paragraph before a task sets it up; the task's `display_prompt` asks the question only and does not restate the scenario.
9. A predict task is never right or wrong. Its feedback says the prediction is saved and where it will be tested.
10. Check and practice feedback explains: the correct message says why it is right; the incorrect message points at what to look for without giving the answer.
11. Do not restate in a callout what the paragraph next to it already said.

Targets (words):

| Element | Target |
|---|---|
| Paragraph | up to 60 |
| Key idea | up to 25 |
| Note body | up to 50 |
| Misconception belief / evidence / conclusion | up to 30 / 45 / 30 |
| List item | up to 30 |
| Task display prompt | up to 25 |
| Feedback message | up to 40 |
| Table cell | up to 12 |
| Prose per section, excluding tasks | 150 to 280 |

### 2.5 Length and shape policy: targets, never gates

This is a hard requirement from the owner.

- Every number in 2.4 is a **target stated in the prompt**. Models follow stated limits closely; that is the whole mechanism.
- Going over a target **never fails a run, never triggers a repair or regeneration call, and never truncates text**. Whatever the writer produced is what ships.
- Overages and shape misses are recorded as advisory warnings on the section record: `length_over_target:<element>:<actual>/<target>`, `shape_missing:key_idea`, `shape_missing:subheading`, `list_item_not_parallel`. They are visible in logs and the teacher-facing issues list at most; they never change READY.
- Audit the existing composer, writer, continuity and QA validators. Any existing check that hard-fails or triggers a repair on length, node count, paragraph runs or callout count (`max_ordinary_nodes`, paragraph-run detection, callout limit) becomes advisory. List each one changed in the PR.
- What stays hard: schema validity; internal id, metadata or placeholder leakage (already hard at the writer); a task with no options or no correct answer where one is required.
- Renderers must cope with any length. Learn simply grows. Print flows to another page; nothing is clipped, shrunk or cut. Tests include an over-long fixture.

### 2.6 The golden fixture

One hand-written shared document, "How Plants Get the Energy to Grow", matching the canvas content and using every block in 2.1 and every markup in 2.2. It is the contract between the parallel tracks: renderer tracks build against it without waiting for the writer; the writer track is judged by how close real output comes to it.

Also keep two more fixtures: `legacy` (the current exported lesson, no new fields) and `overlong` (the golden fixture with every text doubled and targets exceeded).

## 3. Visual tokens

Use the app's existing display serif for the lesson title and quotes. Use Atkinson Hyperlegible (Google Fonts, 400 and 700, italic 400) for all lesson body text in Learn and Print, with a system sans fallback. Do not add other fonts or colours.

| Token | Value | Used for |
|---|---|---|
| ground | `#FAF8F3` | Learn page background |
| ink | `#1C2321` | Text, section rules, task border and header |
| muted | `#5B6460` | Eyebrows, captions, labels |
| rule | `#DDD8CC` | Hairlines, frames |
| rule-strong | `#C9C3B5` | Unselected option border |
| surface | `#FFFFFF` | Figure, table, misconception, task, equation |
| sand | `#F3EEE3` | Note, quote, compare, selected option |
| green | `#1B5E40` | Key idea label, step numerals, "So" row, correct feedback icon |
| green-tint | `#E4F0E8` | Key idea, correct feedback |
| action | `#C2410C` | Primary button only, white bold text |
| print ink / grey / tint | `#111111` / `#767676` / `#EDEDED` | Print text, answer lines, header fills |

Learn metrics: content column max-width 720px, centred, 24px side padding; body 18px / 1.6; title 46px serif; section title 30px bold; subheading 21px bold; labels 14px bold uppercase with 0.08em tracking; captions 15px; 72px between sections; 22px between blocks in a section; subheadings add 14px above; block radius 12 to 14px; options at least 56px tall, buttons at least 48px; no hyphenation (`hyphens: manual`); `text-wrap: pretty` on paragraphs and `balance` on headings.

Print metrics: A4, margins about 16mm; body 12pt; nothing below 9pt; section title 16pt bold; all rules at least 1px; every block must be distinguishable in black and white (never by colour alone).

## 4. Work split

One short contract phase, then four tracks in parallel, then one integration pass.

```text
Phase 0  Contract + fixtures            (one agent, first, small)
   |
   +-- Track A  Learn renderer          (frontend only)
   +-- Track B  Print renderer          (print adapter + templates only)
   +-- Track C  Composer + writer       (prompts, packets, advisory checks)
   +-- Track D  Tasks                   (task contract + authoring + teacher page data)
   |
Phase 5  Integration run + acceptance   (one agent, after all four merge)
```

File ownership, to keep the tracks from colliding:

| Track | Owns | Must not touch |
|---|---|---|
| 0 | Shared document models (`document/shared_lesson/` models), frontend document types, fixtures, the two inline parsers and their tests | Renderers, prompts |
| A | `DocumentCanvas`, node components, `OrderedDocumentList.svelte`, lesson styles (frontend) | Backend, shared models, parsers' grammar |
| B | Shared → Print adapter mappings, print templates and styles, answer-key layout | Learn, shared models, prompts |
| C | `document/shared_lesson/composer.py`, `resources/prompts/section-composer.md`, `resources/prompts/shared-section-writer.md`, composer/writer validators | Renderers, task contract, anything about figures |
| D | Task contract fields, task authoring prompt, Learn task component logic, Print task data | Ordinary-content prompts, non-task renderers |

Coordination with doc 35: it edits `composer.py`, `section-composer.md` and `shared-section-writer.md` for figures. If doc 35 is not merged, Track C branches from the doc 35 branch. Track C never adds, removes or decides a figure.

Track D and Track A both touch the Learn task component: Track A owns its markup and styles, Track D owns its data and behaviour. Track A lands the styled component reading `display_prompt` with a fallback to `prompt`; Track D fills the data.

### Phase 0 — Contract and fixtures

0.1 Add the model changes in 2.3 with defaults; mirror them in the frontend types and any provider/draft schema twin.
0.2 Write the two inline parsers (2.2) and one shared set of test vectors used by both.
0.3 Add the three fixtures (2.6) where both frontend and backend tests can load them.
0.4 Add a dev-only way to open a fixture in the Learn view and to render it through Print to PDF.

**Gate G0** (must pass before the tracks start):
- [ ] `legacy` fixture loads; its content hash equals the stored hash.
- [ ] Golden fixture validates against the models.
- [ ] Both parsers pass the same vectors, including unmatched `**`, a lone `~`, `<script>` in text and an empty string.
- [ ] Existing test suite green.

### Track A — Learn renderer

A1. Fix the losses: split paragraphs on blank lines; ordered lists show numbers; section header (rule, "Part n of N", title) rendered in the body in the All view and in single-section view; tabs and any navigation show `section.title`; remove "DOCUMENT · V2", node counts and any id from the learner view.
A2. Reading column and spacing per section 3. Replace the flat grid gap with the spacing scale.
A3. Implement every block in 2.1 with the tokens in section 3, each as its own component. Apply inline markup everywhere 2.2 lists.
A4. Lesson map under the title: numbered section links.
A5. Task card: header strip with question number (running across the lesson) and mode text by role; lettered options; selected state; primary button label by role ("Lock in my prediction" / "Check my answer"); feedback area that shows `saved` for predict and explanatory text otherwise.
A6. Phone width (390px): single column, compare cards stack, tables scroll inside their frame, no horizontal page scroll.
A7. Missing figure asset: render nothing in the learner view (no dashed placeholder, no "No asset" text). Teacher preview may keep doc 35's "Figure planned" state.

**Gate G1**:
- [ ] Golden fixture in Learn matches the canvas screenshot block for block at 1280px.
- [ ] Screenshot at 390px with no horizontal scroll.
- [ ] `legacy` fixture renders with paragraphs split, numbered list numbered, section titles visible, no ids anywhere on screen.
- [ ] `overlong` fixture renders without overflow or truncation.
- [ ] Keyboard: every option and button reachable with Tab; options are real buttons with a pressed state.
- [ ] Text search of the rendered DOM finds none of: section ids, `shared-node-`, `task-`, "nodes", "V2".

### Track B — Print renderer

B1. Fix the losses: paragraph splits; numbered lists; callouts full width; answer key labelled Q1, Q2; no contents list when the worksheet has fewer than five sections.
B2. Page template: running line with subject and lesson number, name and date lines on page 1, footer with lesson title and "Page n of N", A4 margins.
B3. Print version of every block in 2.1, readable in greyscale. Apply inline markup everywhere.
B4. Task layout by response type: tick circles and lettered options for choice; answer lines for written responses, count sized to the expected answer; "I think this because" line on predict tasks.
B5. Pagination rules: a heading stays with its first paragraph; tasks, figures, tables, equations and misconception boxes do not split across pages; content that does not fit moves to the next page; nothing is clipped or shrunk.
B6. Teacher answer page, separate from learner pages and marked "Teacher copy": per question the answer, the explanatory correct feedback, and `option_notes` as a table when present; predict tasks show "not marked, accept either".

**Gate G2**:
- [ ] PDF of the golden fixture matches the canvas pages in structure (page breaks may differ).
- [ ] Greyscale print of that PDF: every block type still distinguishable.
- [ ] `overlong` fixture: more pages, no clipped or overlapping text.
- [ ] `legacy` fixture prints with paragraphs split and lists numbered.
- [ ] Text search of the PDF finds none of: "Choice-", section ids, `shared-node-`, `task-`.
- [ ] No learner page contains an answer.

### Track C — Composer and writer

C1. Composer vocabulary gains: callout variants, equation, quote, compare. Selection guidance from 2.4 rule 7. Figures stay out of the composer (doc 35).
C2. Writer prompt: the inline markup table (2.2), the shaping rules (2.4), the targets table, and one worked before/after example taken from the photosynthesis lesson (the dense paragraph versus the shaped version).
C3. Writer output schema and packet carry the new node fields.
C4. Advisory checks from 2.5, recorded per section, plus the audit that downgrades existing length and count gates to advisory.
C5. Prompt text states plainly: these are targets; write naturally within them; do not pad to reach a minimum.

**Gate G3** (three fresh generations: the photosynthesis lesson, one maths lesson with a formula, one lesson with a clear comparison):
- [ ] No run failed, repaired or regenerated because of length or shape (confirm from logs; list the advisory warnings raised).
- [ ] Every explaining section has a key idea; no paragraph node is one unbroken block over about 80 words in at least two of the three lessons.
- [ ] Bold key terms present; at least one subscript or superscript rendered correctly in the maths or science lesson.
- [ ] Misconceptions arrive in three parts.
- [ ] At least one equation, table or compare block chosen where the content calls for it.
- [ ] No list contains a summary item.
- [ ] No literal `**`, `~` or `^` visible in rendered output.

### Track D — Tasks

D1. Add `role`, `display_prompt`, role-aware `feedback` and `option_notes` to the task contract with fallbacks (missing `display_prompt` → `prompt`; missing role → today's behaviour).
D2. Task authoring prompt: produce the short `display_prompt`, the role, explanatory feedback (2.4 rules 8 to 10) and a one-line `option_notes` entry per wrong option.
D3. Learn behaviour: predict saves the choice and shows the saved message, with no correct/incorrect state; check and practice show explanatory feedback.
D4. Question numbering runs across the lesson and is identical in Learn, Print and the answer page.

**Gate G4**:
- [ ] In a fresh run, no task prompt repeats more than one sentence of the paragraph above it.
- [ ] A predict task never shows "Correct" or "Not yet".
- [ ] No feedback string equals "Correct." or "Not yet — try again."
- [ ] Old stored tasks still render and can be answered.
- [ ] Q numbers match across Learn, Print and the teacher page.

### Phase 5 — Integration and acceptance

5.1 Merge order: 0, then A and B, then D, then C.
5.2 Generate the photosynthesis lesson end to end on the merged branch; open Learn; download the Print PDF.
5.3 Put the result next to the canvas screenshots and list every difference in the PR, each marked "acceptable" or "to fix".
5.4 `python tools/agent/validate_repo.py --scope all` and `python tools/agent/check_architecture.py --format text` green.

## 5. Final acceptance (owner signs off against this list)

- [ ] A freshly generated lesson, opened in Learn, is recognisably the canvas design: reading column, section headers with part numbers, key idea blocks, three-part misconceptions, task cards with dark headers.
- [ ] The same lesson's PDF is recognisably the canvas worksheet, with a separate teacher answer page.
- [ ] Learn and Print contain the same words for every ordinary block.
- [ ] Paragraph breaks, numbered lists, bold terms, subscripts and equations all render in both.
- [ ] No internal ids, counts, version labels or interaction-type labels are visible to a learner in either.
- [ ] No run failed or re-generated because text was over a target; overages appear only as advisory warnings.
- [ ] Lessons stored before this change still open in Learn and still print.
- [ ] Phone-width Learn has no horizontal scroll.
- [ ] Each gate G0 to G4 has its evidence attached to the PR: screenshots at 1280 and 390, PDFs, the advisory-warning log, the list of gates downgraded to advisory.

## 6. Delivery

One branch per track from the Phase 0 branch; small commits; one PR per track with its gate checklist filled in and evidence attached; no pushes to `main`. If a gate item cannot be met today, the PR says so explicitly and what remains; it is never ticked on intent.

## 7. Kick-off prompts for the agent

Paste the whole of this document first, attach the canvas screenshots, then one of:

- **Phase 0:** "Implement Phase 0 of doc 36 only. Before editing, do section 9 and report what you found. Stop when Gate G0 passes and show the evidence for each item."
- **Track A:** "Implement Track A of doc 36 only, on a branch from the Phase 0 branch. Build against the golden, legacy and overlong fixtures; do not wait for the writer. You own only the files listed for Track A. Stop at Gate G1 with screenshots."
- **Track B:** "Implement Track B of doc 36 only, on a branch from the Phase 0 branch. Build against the three fixtures. You own only the files listed for Track B. Stop at Gate G2 with PDFs."
- **Track C:** "Implement Track C of doc 36 only. Length and shape are targets, never gates (section 2.5); find and downgrade any existing check that contradicts that and list them. Do not touch figures. Stop at Gate G3 with the three generated lessons and the warning log."
- **Track D:** "Implement Track D of doc 36 only. Keep fallbacks for stored tasks. Stop at Gate G4."
- **Phase 5:** "All tracks are merged. Run Phase 5 of doc 36 and produce the difference list and the final acceptance evidence."

Standing instructions for every task: change only what the track owns; if the document and the code disagree, say so and propose, do not improvise; never fail, repair or regenerate on length; never show a placeholder or an internal id to a learner; do not add fonts, colours, libraries or block kinds beyond this document.

## 8. Out of scope

Figure decisions, generation and failure handling (doc 35); image quality; the Print editor's edit mode; progressive reveal, focus states and other Learn interaction design beyond the task card; themes or dark mode; math typesetting beyond subscripts, superscripts and the equation block (no LaTeX); rewriting stored documents; turning any advisory quality finding into a gate.

## 9. Verify first, do not assume

- Exact locations of: the shared document models and their frontend types; the Learn node components and `DocumentCanvas`; the Shared → Print adapter and print templates; the composer and writer validators; the task contract and its authoring prompt.
- Whether callouts already have a `tone` or similar field that `variant` should extend or replace (the export shows `tone: "warning"`).
- Whether the print path is HTML-to-PDF (so CSS break rules apply) or positions page objects itself; B5 is implemented accordingly.
- Whether task fields belong on `TaskAnchor`, `shared_task` or the interaction contract, and which of them is hashed.
- Whether adding optional fields changes the content hash of stored documents. If it would, exclude null defaults from hashing.
- Whether the structured-output provider accepts the added node kinds without extra repair churn; if churn rises, flatten misconception parts into the existing callout with a `variant` only.
- Which existing checks gate on length or counts today (2.5), and where "Correct." / "Not yet — try again." is set.
- Whether doc 35 is merged, and which branch Track C must start from.

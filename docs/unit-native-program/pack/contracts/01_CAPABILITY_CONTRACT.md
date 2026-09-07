# Authoritative capability contract

## Source layout and versioning
Use one authoring record beside each native implementation, or an existing native catalogue entry where that is already authoritative. Generate indices and reverse compatibility maps; never maintain both directions manually.
A proposed shared @lectio/contracts package exposes instructional vocabulary and schema definitions without Svelte, Python runtime or native renderer dependencies. If the repository already provides a suitable neutral home, use it and document the mapping.

Each capability has:
- id, native_path (print|learn), kind (page_form|content|interaction), contract_version.
- purpose and cognitive_job; supported_intents referencing canonical IDs.
- supported_actions referencing canonical learner actions; empty for passive content.
- choose_when, reject_when, prerequisites and bounded capacity constraints.
- payload_schema reference, field guidance, examples and negative cases.
- runtime renderer identity; response schema and evaluator contract for scored interactions.
- allowed configuration and default behaviour; asset requirements and accessibility.
- status and readiness evidence; compatibility/deprecation policy.

Use semantic versioning for incompatible payload or scoring changes and a content hash for exact reproducibility. Old published releases must retain compatible rendering/evaluation or an explicit migration that creates a NEW release. Re-exporting a new package must never change an old release's meaning.

## Human guidance versus enforceable constraints
choose_when/reject_when help semantic selection; encode machine-checkable requirements separately (supported action, asset kinds, cardinality, evaluator support). Do not pretend free text is executable validation.
Schema exactness belongs to the selected payload, not to a generic Record<string, unknown>. Export JSON Schema plus generated backend models where already supported. Validate nested objects, ID uniqueness and cross-references beyond schema where needed.

## Generated views
Teaching: intent definitions, neighbouring boundaries, learner actions. No component IDs, object IDs, layout limits or payload examples.
Selection: eligible IDs, purpose, supported intents/actions, choose/reject guidance, relevant capacities/assets. No entire payload schemas, answer keys or unrelated catalogue.
Writer: chosen capability, exact schema, field guidance, source references and relevant examples.
Runtime: validated payload/config, renderer/evaluator version, reference identities and permitted interaction behaviour.
Export a manifest with versions/hashes. Test export reproducibility excluding timestamps and compare generated copies to source. Consumer cannot widen an absent/empty set.

## Capability registration lifecycle
Author implementation and contract → validate schema/examples → render/evaluate fixtures → register → regenerate exports → consumer compatibility check → make selectable.
Package readiness and consumer execution support are separate explicit facts. A UI-only shell is not generation-ready.
All new shells get a readiness row with source path, data schema, evaluator, authoring support, renderer, keyboard operation, contract export, consumer support and evidence. No blank row counts as success.

## Learn scope
Choice and ImageChoice: use one kind with a presentation variant when evaluation is genuinely identical; do not invent duplicate instructional intents.
MatchPairs: stable IDs, unique source IDs, exact target membership, duplicate submission defense.
Classify: category IDs and membership rules; specify one/multiple category support; evaluator must match declaration.
Sequence: define accepted ordering(s), stable IDs and partial scoring; do not claim support for alternative valid orders unless implemented.
Numeric: finite values, nonnegative tolerance, units policy, invalid-response handling.
ShortResponse: choose and document real text semantics (accepted normalized answers or teacher review). Numeric alias cannot advertise general prose assessment. Never auto-score open reasoning by unsupported matching.
ImageHotspot/DragLabel: image asset identity, coordinate system, target regions, label/target references, accessible keyboard alternative and authoring tools. No guessed regions from an unrelated image.
MultiSelect: selected-ID uniqueness, valid options, false positives and partial scoring.
FillBlank: accepted answers/normalization, blank IDs and response counts.
Existing classic QuizCheck/FillInTheBlank must map to the same evaluator semantics rather than conflicting second definitions.

## Print scope
Keep intent→form mappings and object records authoritative. Complete choose/reject/capacity/writer guidance, schema parity, repeated header and fragmentation tests. Preserve student/teacher views and proper answer placement.
Do not require Learn components to supply Print fallbacks as a condition of Learn readiness.

## Consumer boundary
Native policy may narrow capabilities, select supported options, adjust budgets within hard limits and select a subset. It may not rewrite purpose, schemas or evaluator semantics. Unsupported behaviour is added upstream as a versioned capability change.

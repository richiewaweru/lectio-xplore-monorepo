# Shared preparation and teaching contracts

## Shared spec and skeleton
Shared resource spec owns resource purpose, learning mode, depth, teaching obligations, evidence obligations and permitted instructional vocabulary. Native policies own form/component preferences. Skeleton slot type describes pedagogy; slot instance ID describes one occurrence. Repeated apply/guided slots require distinct IDs, never a dictionary keyed only by role.
Preserve existing mode/knowledge-type selection and teacher-approved variations. Optional misconceptions remain optional; do not fabricate them to fill slots. Scope exclusions and prerequisites remain binding.

## PreparedLesson target
Code-owned fields: preparation_id, schema_version, unit_id, path_version_id/revision, path_lesson_id/revision, concept_ids, objective_hash, preparation_hash, spec/skeleton versions, source IDs and approval state.
Semantic fields: objective, must_establish, must_not_introduce, terminology, prior_established, teacher_actuals, anchor, approved misconception IDs, ordered slot instances, variant/support profile.
No native selected component IDs or form IDs. No print-native document_contract_version masquerading as shared meaning.
Canonical objective/IDs are assigned from Unit records, never reauthored by the LLM. Source material is treated as data, not instructions.

## TeachingPlan target
Code supplies teaching_plan_id, revision, preparation_hash, approval status and stable block IDs.
LLM draft supplies arc, anchor usage, ordered blocks with intent, concrete brief, evidence_refs, rationale and optional learner_action.
An activity brief includes action, task constraints, support_level (guided|independent), intended evidence, relevant concepts, source_item_ids when existing items apply, and dependencies on stimulus/content assets.
A passive block has no artificial interaction. Exact answer/task payload lives in typed authored activity data, not a selection decision.
Include concise before/after continuity information without passing all neighbouring output to writers.
Scope and concept IDs are validated; non-existing references rejected. Every required instructional obligation must be covered. An allowed atypical teaching move needs a recorded rationale; it cannot escape resource legality.

## Questions and activity ownership
Reuse approved typed items unchanged when they fulfil the task; a selector cannot rewrite MCQ into matching.
New rich activity briefs are authored from approved material by a dedicated activity writer after compatible native capability selection, then validated before publication. If an approved task type cannot be expressed on a requested path, report incompatibility; reauthoring requires a versioned reviewable task revision.
Shared task meaning can have different native presentation. An ordered task may be numbered on paper and arranged on screen. Both preserve the expected relationships.
Preserve item-generation card-only context where existing policy requires it; send a task-specific card projection rather than the full lesson/Unit. Question sourcing and teaching approval must have explicit states; no second writer independently invents the same approved item.

## Approvals
Keep Unit approval and existing review checkpoints. Shared teaching approval freezes instructional meaning; native presentation does not reopen it. Material pedagogical changes after approval create a new teaching revision. Teacher edits remain intact; regeneration offers scoped overwrite/merge decisions where edits conflict.
Within designated test Units, executor may act as the teacher to exercise approvals. Do not bulk-approve existing user materials.

## Context isolation
Construct typed input packets from explicit allowlists in code. Never forward entire previous responses. Tests inspect actual serialized provider requests, including system prompts/tool schemas, for leakage.
Teaching excludes native inventory. Selector excludes unapproved content writing. Writer excludes sibling schemas and unrelated task answers; it DOES receive the facts/answer it legitimately needs for its assignment.
Use a short semantic overview for selector rhythm, not the full catalogue.
Locks are stored in code: selector returns block_id→decision; writer returns payload. Rehydration joins immutable identities and checks revision/hash.
Sentinel tests insert unique forbidden identifiers into excluded fields and assert they never appear in outbound requests.

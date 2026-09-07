# Target generation prompt responsibilities
These templates guide application prompts, not Casa execution. Implement typed packet builders and strict output schemas; interpolate only approved fields. Replace placeholders through the existing prompt renderer. Do not paste all this file into every call.

## Unit/path planner
Input: curriculum source, scope, learner context, starting knowledge and available semantic knowledge/mode vocabulary.
Instruction: Build an ordered concept path with one independently assessable capability per lesson. Preserve source scope and explicit prerequisites. Do not select native components, page forms or UI types. Do not drop concepts to meet an arbitrary lesson-count target. Identify uncertainty with source references rather than invent facts.
Output: existing canonical Unit/path draft with code-owned identities materialized after validation.

## Shared structural preparation
Input: locked PathLesson objective/scope, relevant facts, prior actuals, skeleton slot instances, approved variations and optional misconception policy.
Instruction: Establish this lesson's anchor and concrete section purposes. Preserve every fixed slot instance and its sequence. The objective and concept IDs are supplied by code. Return semantic content only; no forms/components. Misconceptions may be absent and must not be fabricated.
Output: semantic preparation draft, joined to backend identities.

## Shared teaching planner
Input: resource identity, locked preparation, compact permitted intent/action guidance, approved task sources, block limits and instructional evidence requirements.
Instruction: Plan the whole lesson coherently. For each block name exact content, learner change and evidence. Where participation serves the objective, specify learner action and support. Reuse the anchor purposefully; avoid repetition and premature disclosure. Use no native capability names. Keep approved item meaning intact. Explain permitted atypical intent choices; never choose outside allowed vocabulary.
Output: arc, ordered semantic block briefs, action/support/evidence, sources/dependencies; code attaches stable IDs.

## Print form selector
Input: locked teaching briefs/order and per-block eligible Print capability cards.
Instruction: Add one suitable native form decision per assigned block. Preserve content/action/support and source ownership. Forms must satisfy their choose/reject conditions and capacity. Consider the whole lesson without manufacturing variety. Never compress away required teaching to fit a form. Report incompatibility if no legal form can fulfil the brief.
Output: decisions keyed by supplied block IDs, form ID, supported placement and concise reason. No question/prose payload.

## Learn native selector
Input: locked teaching briefs/order, learner actions, evidence intent, per-block content and interaction candidates, available assets and budgets.
Instruction: Choose presentation only. Passive content may remain passive. Match a response interface to the actual learner action; never infer an activity from the name of a teaching intent alone. Preserve order/support and reveal boundaries. Do not select absent assets or unsupported evaluation. Choose only from supplied candidates; report required incompatibility rather than inventing a capability.
Output: exact native decisions linked to teaching block IDs and task/asset refs. No generated answers or unrelated components.

## Content writer
Input: single locked capability contract, one brief, relevant approved facts and terminology, source refs and concise continuity.
Instruction: Write only this payload. Fulfil the exact brief at the learner level. Use the assigned schema and field formatting. Do not change objective, identity, selected capability, neighbouring content or approved task sources. Do not add practice to explanation fields.
Output: payload conforming to selected schema; technical identity remains outside the model output.

## Activity writer
Input: one activity brief or approved typed item, relevant card projection, selected response contract, support/evidence requirements and validated stimulus assets.
Instruction: If source is approved, preserve its stem, response relationships, correct answer and meaning under the declared native mapping. Otherwise author the constrained task using approved facts. Define unambiguous expected responses and feedback that explains the relevant concept. Do not leak answer in the visible independent task. Do not invent image targets. Unsupported open-response scoring is not permitted.
Output: selected activity schema with stimulus/response/evaluation data as defined by the package. Backend owns IDs and source bindings.

## Scoped repair
Input: same locked packet/schema, previous invalid output, exact validation errors and remaining repair budget.
Instruction: Correct only these contract violations. Do not change the task, selected capability, objective or source identity. If the brief is impossible under the supplied contract, return the supported incompatibility result rather than altering upstream commitments.

## Semantic review
Input: approved plan, relevant rendered/native content and source facts; no authority to mutate.
Instruction: Check objective coverage, correctness, scaffold-to-independent progression, answer visibility, duplicated teaching and source fidelity. Return issues keyed to stage/block with severity and evidence. Automated schema validation remains separate.
Output: structured review issues. Material semantic failure must be repaired and revalidated before acceptance.

## Deterministic responsibilities
Selection eligibility, identity assignment, assembly, publish validation and authoritative scoring are code-owned. Do not add LLM calls for them. Semantic review supplements checks; it never grants a score to bypass runtime validation.

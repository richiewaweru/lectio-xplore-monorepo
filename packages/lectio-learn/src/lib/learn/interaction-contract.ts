/**
 * Learn interaction contracts.
 * Authored config only — no AI-generated executable UI.
 * Evaluation is deterministic and local; no learner DB persistence here.
 *
 * Two rules hold everywhere in this module:
 *
 * 1. A malformed *config* is an authoring error and surfaces through
 *    `validateInteractionContract` / `InteractionConfigError`.
 * 2. A malformed *response* — unknown id, duplicate id, non-finite number,
 *    wrong response count — throws `InteractionResponseError` instead of being
 *    scored. A forged or impossible response must not produce evidence.
 */

export type InteractionKindId =
	| 'choice'
	| 'multi-select'
	| 'fill-blank'
	| 'numeric'
	| 'short-response'
	| 'match-pairs'
	| 'classify'
	| 'sequence'
	| 'image-hotspot'
	| 'drag-label';

/**
 * `image-choice` is a presentation variant of `choice`, not its own kind:
 * evaluation is identical, only the option rendering differs.
 */
export type ChoicePresentation = 'text' | 'image';

export type AttemptPolicy = {
	/** Max graded attempts; null = unlimited practice. */
	max_attempts: number | null;
	show_feedback_after_submit: boolean;
	allow_retry_after_correct: boolean;
};

export type HintSpec = {
	level: 1 | 2 | 3;
	text: string;
};

export type FeedbackSpec = {
	correct: string;
	incorrect: string;
	partial?: string;
};

export type CompletionRule =
	| { type: 'submitted' }
	| { type: 'correct' }
	| { type: 'score_at_least'; min_ratio: number };

/** Serializable interaction definition (authored). */
export interface LearnInteractionContract {
	id: string;
	kind: InteractionKindId;
	prompt: string;
	assessment_mode: 'practice' | 'graded';
	attempt_policy: AttemptPolicy;
	hints?: HintSpec[];
	feedback: FeedbackSpec;
	completion: CompletionRule;
	/** Kind-specific authored payload (strictly validated per kind). */
	config: Record<string, unknown>;
	accessibility?: {
		aria_label?: string;
		narration?: 'none' | 'optional' | 'recommended';
		keyboard_operable: boolean;
	};
	/** Explicit rule: config is data; runtime must not execute AI-authored code. */
	ai_config_rule: 'config-only';
}

/**
 * `pending-review` is a real outcome, not a scoring failure: a teacher-reviewed
 * short response is submitted and awaiting judgement. It never carries earned
 * score, so it cannot inflate auto-scored evidence.
 */
export type EvaluationOutcome = 'correct' | 'incorrect' | 'partial' | 'pending-review';

export interface EvaluationResult {
	outcome: EvaluationOutcome;
	score_earned: number;
	score_possible: number;
	feedback: string;
	details?: Record<string, unknown>;
}

export interface InteractionAttemptState {
	interaction_id: string;
	attempt_count: number;
	last_result: EvaluationResult | null;
	completed: boolean;
	responses: unknown[];
}

/** A learner response that cannot be scored: unknown, duplicate or malformed. */
export class InteractionResponseError extends Error {
	constructor(
		message: string,
		readonly code:
			| 'invalid-response'
			| 'unknown-response-id'
			| 'duplicate-response-id'
			| 'response-count-mismatch'
	) {
		super(message);
		this.name = 'InteractionResponseError';
	}
}

/** An authored config that cannot be evaluated as declared. */
export class InteractionConfigError extends Error {
	constructor(message: string) {
		super(message);
		this.name = 'InteractionConfigError';
	}
}

const DEFAULT_ATTEMPT_POLICY: AttemptPolicy = {
	max_attempts: null,
	show_feedback_after_submit: true,
	allow_retry_after_correct: true
};

export function createAttemptState(interactionId: string): InteractionAttemptState {
	return {
		interaction_id: interactionId,
		attempt_count: 0,
		last_result: null,
		completed: false,
		responses: []
	};
}

function asStringArray(value: unknown): string[] {
	if (!Array.isArray(value)) return [];
	return value.map((v) => String(v));
}

function normalizeText(value: string): string {
	return value.trim().toLowerCase().replace(/\s+/g, ' ');
}

function normalizeAnswer(value: string, caseSensitive: boolean): string {
	const collapsed = value.trim().replace(/\s+/g, ' ');
	return caseSensitive ? collapsed : collapsed.toLowerCase();
}

function optionIdSet(options: unknown): Set<string> | null {
	if (!Array.isArray(options) || options.length === 0) return null;
	const ids = options.map((option) =>
		option && typeof option === 'object' && 'id' in option
			? String((option as { id: unknown }).id)
			: String(option)
	);
	return new Set(ids);
}

function requireNonEmptyString(value: unknown, field: string): string {
	if (typeof value !== 'string' || value.trim() === '') {
		throw new InteractionResponseError(`${field} must be a non-empty string`, 'invalid-response');
	}
	return value;
}

function requireStringArray(value: unknown, field: string): string[] {
	if (!Array.isArray(value) || value.some((item) => typeof item !== 'string')) {
		throw new InteractionResponseError(`${field} must be an array of strings`, 'invalid-response');
	}
	return value as string[];
}

function rejectDuplicates(ids: string[], field: string): void {
	if (new Set(ids).size !== ids.length) {
		throw new InteractionResponseError(`${field} contains duplicate ids`, 'duplicate-response-id');
	}
}

function rejectUnknown(ids: string[], known: Set<string> | null, field: string): void {
	if (!known) return;
	for (const id of ids) {
		if (!known.has(id)) {
			throw new InteractionResponseError(
				`${field} references unknown id "${id}"`,
				'unknown-response-id'
			);
		}
	}
}

function gradedFeedback(outcome: EvaluationOutcome, feedback: FeedbackSpec): string {
	if (outcome === 'correct') return feedback.correct;
	if (outcome === 'partial') return feedback.partial ?? feedback.incorrect;
	return feedback.incorrect;
}

function partialOutcome(earned: number, possible: number): EvaluationOutcome {
	if (possible > 0 && earned === possible) return 'correct';
	return earned > 0 ? 'partial' : 'incorrect';
}

// ── Evaluators ──────────────────────────────────────────────────────────────

export function evaluateChoice(
	config: { correct_option_id: string; options?: Array<{ id: string } | string> },
	response: { selected_option_id: string },
	feedback: FeedbackSpec
): EvaluationResult {
	const known = optionIdSet(config.options);
	if (known && !known.has(config.correct_option_id)) {
		throw new InteractionConfigError(
			`correct_option_id "${config.correct_option_id}" is not one of the declared options`
		);
	}
	const selected = requireNonEmptyString(response?.selected_option_id, 'selected_option_id');
	rejectUnknown([selected], known, 'selected_option_id');

	const ok = selected === config.correct_option_id;
	return {
		outcome: ok ? 'correct' : 'incorrect',
		score_earned: ok ? 1 : 0,
		score_possible: 1,
		feedback: ok ? feedback.correct : feedback.incorrect,
		details: { selected_option_id: selected }
	};
}

export function evaluateMultiSelect(
	config: { correct_option_ids: string[]; options?: Array<{ id: string } | string> },
	response: { selected_option_ids: string[] },
	feedback: FeedbackSpec
): EvaluationResult {
	const correctIds = requireStringArrayConfig(config.correct_option_ids, 'correct_option_ids');
	const known = optionIdSet(config.options);
	rejectUnknownConfig(correctIds, known, 'correct_option_ids');

	const selectedIds = requireStringArray(response?.selected_option_ids, 'selected_option_ids');
	rejectDuplicates(selectedIds, 'selected_option_ids');
	rejectUnknown(selectedIds, known, 'selected_option_ids');

	const correct = new Set(correctIds);
	const selected = new Set(selectedIds);
	let hits = 0;
	for (const id of selected) {
		if (correct.has(id)) hits += 1;
	}
	const falsePositives = [...selected].filter((id) => !correct.has(id)).length;
	const score_possible = correct.size;
	const score_earned = Math.max(0, hits - falsePositives);
	let outcome: EvaluationOutcome = 'incorrect';
	if (score_earned === score_possible && falsePositives === 0 && selected.size === correct.size) {
		outcome = 'correct';
	} else if (score_earned > 0) {
		outcome = 'partial';
	}
	return {
		outcome,
		score_earned,
		score_possible,
		feedback: gradedFeedback(outcome, feedback),
		details: { false_positives: falsePositives }
	};
}

function requireStringArrayConfig(value: unknown, field: string): string[] {
	if (!Array.isArray(value) || value.length === 0) {
		throw new InteractionConfigError(`${field} must be a non-empty array`);
	}
	return value.map((item) => String(item));
}

function rejectUnknownConfig(ids: string[], known: Set<string> | null, field: string): void {
	if (!known) return;
	for (const id of ids) {
		if (!known.has(id)) {
			throw new InteractionConfigError(`${field} references undeclared option "${id}"`);
		}
	}
}

/** One accepted answer, or a list of alternatives, per blank. */
export type BlankAnswer = string | string[];

export function evaluateFillBlank(
	config: { answers: BlankAnswer[]; blank_ids?: string[]; case_sensitive?: boolean },
	response: { blanks: string[] },
	feedback: FeedbackSpec
): EvaluationResult {
	if (!Array.isArray(config.answers) || config.answers.length === 0) {
		throw new InteractionConfigError('fill-blank config requires a non-empty answers[]');
	}
	if (config.blank_ids && config.blank_ids.length !== config.answers.length) {
		throw new InteractionConfigError('blank_ids must have one id per answer');
	}
	const blanks = requireStringArray(response?.blanks, 'blanks');
	if (blanks.length !== config.answers.length) {
		throw new InteractionResponseError(
			`expected ${config.answers.length} blank response(s), received ${blanks.length}`,
			'response-count-mismatch'
		);
	}

	const caseSensitive = config.case_sensitive === true;
	const score_possible = config.answers.length;
	let score_earned = 0;
	const per_blank: Array<{ id: string; correct: boolean }> = [];

	config.answers.forEach((answer, index) => {
		const accepted = (Array.isArray(answer) ? answer : [answer]).map((value) =>
			normalizeAnswer(String(value), caseSensitive)
		);
		const given = normalizeAnswer(blanks[index] ?? '', caseSensitive);
		const correct = accepted.includes(given);
		if (correct) score_earned += 1;
		per_blank.push({ id: config.blank_ids?.[index] ?? String(index), correct });
	});

	const outcome = partialOutcome(score_earned, score_possible);
	return {
		outcome,
		score_earned,
		score_possible,
		feedback: gradedFeedback(outcome, feedback),
		details: { per_blank }
	};
}

export function evaluateNumeric(
	config: { value: number; tolerance?: number; unit?: string },
	response: { value: number },
	feedback: FeedbackSpec
): EvaluationResult {
	if (typeof config.value !== 'number' || !Number.isFinite(config.value)) {
		throw new InteractionConfigError('numeric config value must be a finite number');
	}
	if (config.tolerance !== undefined) {
		if (typeof config.tolerance !== 'number' || !Number.isFinite(config.tolerance)) {
			throw new InteractionConfigError('numeric tolerance must be a finite number');
		}
		if (config.tolerance < 0) {
			throw new InteractionConfigError('numeric tolerance must not be negative');
		}
	}
	const given = response?.value;
	if (typeof given !== 'number' || !Number.isFinite(given)) {
		throw new InteractionResponseError(
			'numeric response value must be a finite number',
			'invalid-response'
		);
	}

	const tol = config.tolerance ?? 0;
	const ok = Math.abs(given - config.value) <= tol;
	return {
		outcome: ok ? 'correct' : 'incorrect',
		score_earned: ok ? 1 : 0,
		score_possible: 1,
		feedback: ok ? feedback.correct : feedback.incorrect,
		details: { value: given, tolerance: tol, unit: config.unit ?? null }
	};
}

/**
 * How a short written response is judged. There is no third option: either the
 * author declared the answers that count, or a teacher reads it.
 */
export type ShortResponseEvaluationMode = 'accepted-answers' | 'teacher-review';

export interface ShortResponseConfig {
	evaluation: ShortResponseEvaluationMode;
	/** Required for `accepted-answers`; the full set that scores as correct. */
	accepted_answers?: string[];
	/** Default false: answers are compared after trim + whitespace + case folding. */
	case_sensitive?: boolean;
	/** What a teacher should look for. Only meaningful for `teacher-review`. */
	review_guidance?: string;
	max_words?: number;
}

/**
 * Short response, with real text semantics.
 *
 * `accepted-answers` compares the normalized response against a declared set —
 * legitimate for a term, a name or a short phrase. `teacher-review` returns
 * `pending-review` and scores nothing. Open reasoning is never auto-scored by
 * string matching, which is what the previous numeric alias amounted to.
 */
export function evaluateShortResponse(
	config: ShortResponseConfig,
	response: { text: string },
	feedback: FeedbackSpec
): EvaluationResult {
	const text = requireNonEmptyString(response?.text, 'text');

	if (config.evaluation === 'teacher-review') {
		return {
			outcome: 'pending-review',
			score_earned: 0,
			score_possible: 1,
			feedback: feedback.partial ?? 'Submitted for teacher review.',
			details: {
				mode: 'teacher-review',
				review_guidance: config.review_guidance ?? null,
				text
			}
		};
	}

	if (config.evaluation !== 'accepted-answers') {
		throw new InteractionConfigError(
			`short-response evaluation must be 'accepted-answers' or 'teacher-review', received "${String(config.evaluation)}"`
		);
	}
	if (!Array.isArray(config.accepted_answers) || config.accepted_answers.length === 0) {
		throw new InteractionConfigError(
			'short-response accepted-answers mode requires a non-empty accepted_answers[]'
		);
	}

	const caseSensitive = config.case_sensitive === true;
	const accepted = config.accepted_answers.map((answer) =>
		normalizeAnswer(String(answer), caseSensitive)
	);
	const ok = accepted.includes(normalizeAnswer(text, caseSensitive));
	return {
		outcome: ok ? 'correct' : 'incorrect',
		score_earned: ok ? 1 : 0,
		score_possible: 1,
		feedback: ok ? feedback.correct : feedback.incorrect,
		details: { mode: 'accepted-answers', text }
	};
}

export function evaluateMatchPairs(
	config: { pairs: Array<{ left: string; right: string }> },
	response: { matches: Array<{ left: string; right: string }> },
	feedback: FeedbackSpec
): EvaluationResult {
	if (!Array.isArray(config.pairs) || config.pairs.length === 0) {
		throw new InteractionConfigError('match-pairs config requires a non-empty pairs[]');
	}
	const lefts = config.pairs.map((pair) => String(pair.left));
	if (new Set(lefts).size !== lefts.length) {
		throw new InteractionConfigError('match-pairs source ids must be unique');
	}
	const expected = new Map(config.pairs.map((pair) => [String(pair.left), String(pair.right)]));
	const validTargets = new Set(config.pairs.map((pair) => String(pair.right)));

	if (!Array.isArray(response?.matches)) {
		throw new InteractionResponseError('matches must be an array', 'invalid-response');
	}
	const submittedLefts = response.matches.map((match) =>
		requireNonEmptyString(match?.left, 'match.left')
	);
	rejectDuplicates(submittedLefts, 'matches');
	rejectUnknown(submittedLefts, new Set(expected.keys()), 'match.left');
	rejectUnknown(
		response.matches.map((match) => requireNonEmptyString(match?.right, 'match.right')),
		validTargets,
		'match.right'
	);

	const score_possible = expected.size;
	let score_earned = 0;
	for (const match of response.matches) {
		if (expected.get(String(match.left)) === String(match.right)) score_earned += 1;
	}
	const outcome = partialOutcome(score_earned, score_possible);
	return {
		outcome,
		score_earned,
		score_possible,
		feedback: gradedFeedback(outcome, feedback)
	};
}

export function evaluateSequence(
	config: { order: string[] },
	response: { order: string[] },
	feedback: FeedbackSpec
): EvaluationResult {
	if (!Array.isArray(config.order) || config.order.length === 0) {
		throw new InteractionConfigError('sequence config requires a non-empty order[]');
	}
	const expected = config.order.map((id) => String(id));
	if (new Set(expected).size !== expected.length) {
		throw new InteractionConfigError('sequence item ids must be unique');
	}

	const given = requireStringArray(response?.order, 'order');
	rejectDuplicates(given, 'order');
	if (given.length !== expected.length) {
		throw new InteractionResponseError(
			`expected ${expected.length} ordered item(s), received ${given.length}`,
			'response-count-mismatch'
		);
	}
	rejectUnknown(given, new Set(expected), 'order');

	let score_earned = 0;
	expected.forEach((id, index) => {
		if (given[index] === id) score_earned += 1;
	});
	const outcome = partialOutcome(score_earned, expected.length);
	return {
		outcome,
		score_earned,
		score_possible: expected.length,
		feedback: gradedFeedback(outcome, feedback)
	};
}

export function evaluateInteraction(
	contract: LearnInteractionContract,
	response: unknown
): EvaluationResult {
	const feedback = contract.feedback;
	switch (contract.kind) {
		case 'choice':
		// image-choice is a presentation variant of choice; identical evaluation.
		case 'image-hotspot':
			return evaluateChoice(
				contract.config as { correct_option_id: string },
				response as { selected_option_id: string },
				feedback
			);
		case 'multi-select':
			return evaluateMultiSelect(
				contract.config as { correct_option_ids: string[] },
				response as { selected_option_ids: string[] },
				feedback
			);
		case 'fill-blank':
			return evaluateFillBlank(
				contract.config as { answers: BlankAnswer[] },
				response as { blanks: string[] },
				feedback
			);
		case 'numeric':
			return evaluateNumeric(
				contract.config as { value: number; tolerance?: number },
				response as { value: number },
				feedback
			);
		case 'short-response':
			return evaluateShortResponse(
				contract.config as unknown as ShortResponseConfig,
				response as { text: string },
				feedback
			);
		case 'match-pairs':
		// classify declares single-category membership, so item→category links
		// evaluate exactly as source→target pairs.
		case 'classify':
		case 'drag-label':
			return evaluateMatchPairs(
				contract.config as { pairs: Array<{ left: string; right: string }> },
				response as { matches: Array<{ left: string; right: string }> },
				feedback
			);
		case 'sequence':
			return evaluateSequence(
				contract.config as { order: string[] },
				response as { order: string[] },
				feedback
			);
		default: {
			const _exhaustive: never = contract.kind;
			throw new InteractionConfigError(
				`Unsupported interaction kind: ${String(_exhaustive)}`
			);
		}
	}
}

export function isComplete(result: EvaluationResult, rule: CompletionRule): boolean {
	switch (rule.type) {
		case 'submitted':
			return true;
		case 'correct':
			return result.outcome === 'correct';
		case 'score_at_least':
			return (
				result.score_possible > 0 &&
				result.score_earned / result.score_possible >= rule.min_ratio
			);
	}
}

export function recordAttempt(
	state: InteractionAttemptState,
	contract: LearnInteractionContract,
	response: unknown
): InteractionAttemptState {
	const max = contract.attempt_policy.max_attempts;
	if (max !== null && state.attempt_count >= max) {
		return state;
	}
	if (
		state.last_result?.outcome === 'correct' &&
		contract.attempt_policy.allow_retry_after_correct === false
	) {
		return state;
	}
	const result = evaluateInteraction(contract, response);
	const attempt_count = state.attempt_count + 1;
	const completed = isComplete(result, contract.completion);
	return {
		interaction_id: state.interaction_id,
		attempt_count,
		last_result: result,
		completed,
		responses: [...state.responses, response]
	};
}

// ── Contract validation ─────────────────────────────────────────────────────

function validateOptionSet(
	config: Record<string, unknown>,
	errors: string[],
	kind: string
): Set<string> | null {
	const options = config.options;
	if (!Array.isArray(options) || options.length < 2) {
		errors.push(`${kind} requires options[] with at least two declared ids`);
		return null;
	}
	const ids = options.map((option) =>
		option && typeof option === 'object' && 'id' in option
			? String((option as { id: unknown }).id)
			: String(option)
	);
	if (ids.some((id) => id.trim() === '')) errors.push(`${kind} option ids must be non-empty`);
	if (new Set(ids).size !== ids.length) errors.push(`${kind} option ids must be unique`);
	return new Set(ids);
}

export function validateInteractionContract(contract: LearnInteractionContract): string[] {
	const errors: string[] = [];
	if (!contract.id?.trim()) errors.push('id is required');
	if (!contract.prompt?.trim()) errors.push('prompt is required');
	if (contract.ai_config_rule !== 'config-only') {
		errors.push('ai_config_rule must be config-only (no executable AI UI)');
	}
	if (!contract.feedback?.correct || !contract.feedback?.incorrect) {
		errors.push('feedback.correct and feedback.incorrect are required');
	}
	if (contract.accessibility && contract.accessibility.keyboard_operable !== true) {
		errors.push('new interactions must declare keyboard_operable: true');
	}

	const policy = contract.attempt_policy;
	if (!policy) {
		errors.push('attempt_policy is required');
	} else if (
		policy.max_attempts !== null &&
		(!Number.isInteger(policy.max_attempts) || policy.max_attempts < 1)
	) {
		errors.push('attempt_policy.max_attempts must be null or a positive integer');
	}

	if (contract.completion?.type === 'score_at_least') {
		const ratio = contract.completion.min_ratio;
		if (typeof ratio !== 'number' || !Number.isFinite(ratio) || ratio < 0 || ratio > 1) {
			errors.push('completion.min_ratio must be a finite number between 0 and 1');
		}
	}

	const config = contract.config ?? {};
	switch (contract.kind) {
		case 'choice': {
			const declared = validateOptionSet(config, errors, 'choice');
			const correct = config.correct_option_id;
			if (typeof correct !== 'string' || correct.trim() === '') {
				errors.push('choice requires correct_option_id');
			} else if (declared && !declared.has(correct)) {
				errors.push(`choice correct_option_id "${correct}" is not a declared option`);
			}
			break;
		}
		case 'image-hotspot': {
			// Spatial kinds are declared unavailable in the capability catalogue
			// because coordinate authoring does not exist. What is specifiable is
			// still checked so a hand-authored fixture cannot be silently wrong.
			if (!config.correct_option_id) errors.push('image-hotspot requires correct_option_id');
			if (Array.isArray(config.regions)) {
				const ids = asStringArray(
					(config.regions as Array<{ id?: unknown }>).map((region) => region?.id)
				);
				if (new Set(ids).size !== ids.length) {
					errors.push('image-hotspot region ids must be unique');
				}
				if (!ids.includes(String(config.correct_option_id))) {
					errors.push('image-hotspot correct_option_id must name a declared region');
				}
			}
			break;
		}
		case 'multi-select': {
			const declared = validateOptionSet(config, errors, 'multi-select');
			const correct = config.correct_option_ids;
			if (!Array.isArray(correct) || correct.length === 0) {
				errors.push('multi-select requires a non-empty correct_option_ids[]');
			} else {
				const ids = asStringArray(correct);
				if (new Set(ids).size !== ids.length) {
					errors.push('multi-select correct_option_ids must be unique');
				}
				if (declared) {
					for (const id of ids) {
						if (!declared.has(id)) {
							errors.push(`multi-select correct_option_ids names undeclared option "${id}"`);
						}
					}
				}
			}
			break;
		}
		case 'fill-blank': {
			const answers = config.answers;
			if (!Array.isArray(answers) || answers.length < 1) {
				errors.push('fill-blank requires answers[]');
				break;
			}
			answers.forEach((answer, index) => {
				const accepted = Array.isArray(answer) ? answer : [answer];
				if (accepted.length === 0 || accepted.some((value) => String(value).trim() === '')) {
					errors.push(`fill-blank answer ${index} must declare at least one non-empty answer`);
				}
			});
			if (config.blank_ids !== undefined) {
				const ids = asStringArray(config.blank_ids);
				if (ids.length !== answers.length) {
					errors.push('fill-blank blank_ids must have one id per answer');
				}
				if (new Set(ids).size !== ids.length) {
					errors.push('fill-blank blank_ids must be unique');
				}
			}
			break;
		}
		case 'numeric': {
			if (typeof config.value !== 'number' || !Number.isFinite(config.value)) {
				errors.push('numeric requires a finite value:number');
			}
			if (config.tolerance !== undefined) {
				const tolerance = config.tolerance;
				if (typeof tolerance !== 'number' || !Number.isFinite(tolerance)) {
					errors.push('numeric tolerance must be a finite number');
				} else if (tolerance < 0) {
					errors.push('numeric tolerance must not be negative');
				}
			}
			break;
		}
		case 'short-response': {
			const mode = config.evaluation;
			if (mode !== 'accepted-answers' && mode !== 'teacher-review') {
				errors.push(
					"short-response requires evaluation: 'accepted-answers' | 'teacher-review' (a numeric value is not a text answer)"
				);
				break;
			}
			if (mode === 'accepted-answers') {
				const accepted = config.accepted_answers;
				if (!Array.isArray(accepted) || accepted.length === 0) {
					errors.push('short-response accepted-answers requires a non-empty accepted_answers[]');
				} else {
					const normalized = accepted.map((answer) => normalizeText(String(answer)));
					if (normalized.some((answer) => answer === '')) {
						errors.push('short-response accepted_answers must not contain blank answers');
					}
					if (new Set(normalized).size !== normalized.length) {
						errors.push('short-response accepted_answers must be unique after normalization');
					}
				}
			}
			if (mode === 'teacher-review' && contract.completion?.type === 'correct') {
				errors.push(
					'short-response teacher-review cannot complete on correctness; no automatic score exists'
				);
			}
			break;
		}
		case 'match-pairs':
		case 'classify':
		case 'drag-label': {
			const pairs = config.pairs;
			if (!Array.isArray(pairs) || pairs.length === 0) {
				errors.push('match-pairs requires a non-empty pairs[]');
				break;
			}
			const lefts = asStringArray((pairs as Array<{ left?: unknown }>).map((pair) => pair?.left));
			const rights = asStringArray(
				(pairs as Array<{ right?: unknown }>).map((pair) => pair?.right)
			);
			if (lefts.some((left) => left.trim() === '' || left === 'undefined')) {
				errors.push('match-pairs every pair requires a source id');
			}
			if (rights.some((right) => right.trim() === '' || right === 'undefined')) {
				errors.push('match-pairs every pair requires a target id');
			}
			if (new Set(lefts).size !== lefts.length) {
				errors.push('match-pairs source ids must be unique');
			}
			break;
		}
		case 'sequence': {
			const order = config.order;
			if (!Array.isArray(order) || order.length === 0) {
				errors.push('sequence requires a non-empty order[]');
				break;
			}
			const ids = asStringArray(order);
			if (ids.some((id) => id.trim() === '')) errors.push('sequence item ids must be non-empty');
			if (new Set(ids).size !== ids.length) errors.push('sequence item ids must be unique');
			break;
		}
	}
	return errors;
}

// ── Classic content adapters ────────────────────────────────────────────────

/** Build a choice contract from existing QuizContent (upgrade path). */
export function quizContentToInteractionContract(
	quiz: {
		question: string;
		options: Array<{ text: string; correct: boolean }>;
		feedback_correct: string;
		feedback_incorrect: string;
	},
	id = 'quiz-check'
): LearnInteractionContract {
	const correctIndex = quiz.options.findIndex((option) => option.correct);
	if (correctIndex < 0) {
		throw new InteractionConfigError('quiz-check requires exactly one correct option');
	}
	if (quiz.options.filter((option) => option.correct).length > 1) {
		throw new InteractionConfigError(
			'quiz-check declares more than one correct option; use multi-select instead'
		);
	}
	return {
		id,
		kind: 'choice',
		prompt: quiz.question,
		assessment_mode: 'graded',
		attempt_policy: { ...DEFAULT_ATTEMPT_POLICY, max_attempts: 2 },
		feedback: {
			correct: quiz.feedback_correct,
			incorrect: quiz.feedback_incorrect
		},
		completion: { type: 'submitted' },
		config: {
			correct_option_id: String(correctIndex),
			options: quiz.options.map((option, index) => ({ id: String(index), text: option.text }))
		},
		accessibility: {
			aria_label: quiz.question,
			narration: 'optional',
			keyboard_operable: true
		},
		ai_config_rule: 'config-only'
	};
}

export function fillBlankContentToInteractionContract(
	content: {
		instruction?: string;
		segments: Array<{ is_blank: boolean; answer?: string; text: string }>;
	},
	id = 'fill-in-blank'
): LearnInteractionContract {
	const blanks = content.segments.filter((segment) => segment.is_blank);
	if (blanks.length === 0) {
		throw new InteractionConfigError('fill-in-blank requires at least one blank segment');
	}
	return {
		id,
		kind: 'fill-blank',
		prompt: content.instruction ?? 'Complete the blanks',
		assessment_mode: 'practice',
		attempt_policy: DEFAULT_ATTEMPT_POLICY,
		feedback: {
			correct: 'All blanks correct.',
			incorrect: 'Check the blanks and try again.',
			partial: 'Some blanks are correct.'
		},
		completion: { type: 'score_at_least', min_ratio: 1 },
		config: {
			answers: blanks.map((segment) => segment.answer ?? ''),
			blank_ids: blanks.map((_, index) => `blank-${index + 1}`)
		},
		accessibility: {
			aria_label: content.instruction ?? 'Fill in the blank',
			narration: 'optional',
			keyboard_operable: true
		},
		ai_config_rule: 'config-only'
	};
}

/**
 * Build a short-response contract with explicit text semantics.
 *
 * There is no default: the caller states whether the answers are enumerable or
 * a teacher reads the response.
 */
export function shortResponseToInteractionContract(
	content: {
		prompt: string;
		evaluation: ShortResponseEvaluationMode;
		accepted_answers?: string[];
		review_guidance?: string;
		case_sensitive?: boolean;
		feedback?: Partial<FeedbackSpec>;
	},
	id = 'short-response'
): LearnInteractionContract {
	const teacherReview = content.evaluation === 'teacher-review';
	const config: ShortResponseConfig = teacherReview
		? { evaluation: 'teacher-review', review_guidance: content.review_guidance }
		: {
				evaluation: 'accepted-answers',
				accepted_answers: content.accepted_answers ?? [],
				case_sensitive: content.case_sensitive === true
			};

	return {
		id,
		kind: 'short-response',
		prompt: content.prompt,
		assessment_mode: teacherReview ? 'practice' : 'graded',
		attempt_policy: teacherReview
			? { ...DEFAULT_ATTEMPT_POLICY, max_attempts: 1 }
			: { ...DEFAULT_ATTEMPT_POLICY, max_attempts: 2 },
		feedback: {
			correct: content.feedback?.correct ?? 'Correct.',
			incorrect: content.feedback?.incorrect ?? 'Not quite — check your wording.',
			partial: content.feedback?.partial ?? 'Submitted for teacher review.'
		},
		completion: { type: 'submitted' },
		config: config as unknown as Record<string, unknown>,
		accessibility: {
			aria_label: content.prompt,
			narration: 'optional',
			keyboard_operable: true
		},
		ai_config_rule: 'config-only'
	};
}

export function serializeInteractionContract(contract: LearnInteractionContract): string {
	return JSON.stringify(contract);
}

export function parseInteractionContract(raw: string): LearnInteractionContract {
	const parsed = JSON.parse(raw) as LearnInteractionContract;
	const errors = validateInteractionContract(parsed);
	if (errors.length) {
		throw new Error(`Invalid LearnInteractionContract: ${errors.join('; ')}`);
	}
	return parsed;
}

/** In-memory fixture lesson completion across required interactions. */
export function completeLessonInMemory(
	contracts: LearnInteractionContract[],
	responses: Record<string, unknown>
): {
	completed: boolean;
	states: InteractionAttemptState[];
	score_earned: number;
	score_possible: number;
} {
	const states: InteractionAttemptState[] = [];
	let score_earned = 0;
	let score_possible = 0;
	for (const contract of contracts) {
		let state = createAttemptState(contract.id);
		const response = responses[contract.id];
		if (response !== undefined) {
			state = recordAttempt(state, contract, response);
		}
		states.push(state);
		if (state.last_result) {
			score_earned += state.last_result.score_earned;
			score_possible += state.last_result.score_possible;
		} else {
			score_possible += 1;
		}
	}
	const required = contracts.filter((contract) => contract.assessment_mode === 'graded');
	const completed = required.every(
		(contract) => states.find((state) => state.interaction_id === contract.id)?.completed
	);
	return { completed, states, score_earned, score_possible };
}

export function asStringList(value: unknown): string[] {
	return asStringArray(value);
}

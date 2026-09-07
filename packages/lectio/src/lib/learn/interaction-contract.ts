/**
 * Learn interaction contracts (Phase 04).
 * Authored config only — no AI-generated executable UI.
 * Evaluation is deterministic and local; no learner DB persistence here.
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

export type EvaluationOutcome = 'correct' | 'incorrect' | 'partial';

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

export function evaluateChoice(
	config: { correct_option_id: string },
	response: { selected_option_id: string },
	feedback: FeedbackSpec
): EvaluationResult {
	const ok = response.selected_option_id === config.correct_option_id;
	return {
		outcome: ok ? 'correct' : 'incorrect',
		score_earned: ok ? 1 : 0,
		score_possible: 1,
		feedback: ok ? feedback.correct : feedback.incorrect,
		details: { selected_option_id: response.selected_option_id }
	};
}

export function evaluateMultiSelect(
	config: { correct_option_ids: string[] },
	response: { selected_option_ids: string[] },
	feedback: FeedbackSpec
): EvaluationResult {
	const correct = new Set(config.correct_option_ids);
	const selected = new Set(response.selected_option_ids);
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
	const message =
		outcome === 'correct'
			? feedback.correct
			: outcome === 'partial'
				? (feedback.partial ?? feedback.incorrect)
				: feedback.incorrect;
	return { outcome, score_earned, score_possible, feedback: message };
}

export function evaluateFillBlank(
	config: { answers: string[] },
	response: { blanks: string[] },
	feedback: FeedbackSpec
): EvaluationResult {
	const score_possible = config.answers.length;
	let score_earned = 0;
	config.answers.forEach((answer, i) => {
		if (normalizeText(response.blanks[i] ?? '') === normalizeText(answer)) {
			score_earned += 1;
		}
	});
	const outcome: EvaluationOutcome =
		score_earned === score_possible ? 'correct' : score_earned > 0 ? 'partial' : 'incorrect';
	return {
		outcome,
		score_earned,
		score_possible,
		feedback:
			outcome === 'correct'
				? feedback.correct
				: outcome === 'partial'
					? (feedback.partial ?? feedback.incorrect)
					: feedback.incorrect
	};
}

export function evaluateNumeric(
	config: { value: number; tolerance?: number },
	response: { value: number },
	feedback: FeedbackSpec
): EvaluationResult {
	const tol = config.tolerance ?? 0;
	const ok = Math.abs(response.value - config.value) <= tol;
	return {
		outcome: ok ? 'correct' : 'incorrect',
		score_earned: ok ? 1 : 0,
		score_possible: 1,
		feedback: ok ? feedback.correct : feedback.incorrect
	};
}

export function evaluateMatchPairs(
	config: { pairs: Array<{ left: string; right: string }> },
	response: { matches: Array<{ left: string; right: string }> },
	feedback: FeedbackSpec
): EvaluationResult {
	const expected = new Map(config.pairs.map((p) => [p.left, p.right]));
	const score_possible = expected.size;
	let score_earned = 0;
	for (const m of response.matches) {
		if (expected.get(m.left) === m.right) score_earned += 1;
	}
	const outcome: EvaluationOutcome =
		score_earned === score_possible ? 'correct' : score_earned > 0 ? 'partial' : 'incorrect';
	return {
		outcome,
		score_earned,
		score_possible,
		feedback:
			outcome === 'correct'
				? feedback.correct
				: outcome === 'partial'
					? (feedback.partial ?? feedback.incorrect)
					: feedback.incorrect
	};
}

export function evaluateSequence(
	config: { order: string[] },
	response: { order: string[] },
	feedback: FeedbackSpec
): EvaluationResult {
	const score_possible = config.order.length;
	let score_earned = 0;
	config.order.forEach((id, i) => {
		if (response.order[i] === id) score_earned += 1;
	});
	const outcome: EvaluationOutcome =
		score_earned === score_possible ? 'correct' : score_earned > 0 ? 'partial' : 'incorrect';
	return {
		outcome,
		score_earned,
		score_possible,
		feedback:
			outcome === 'correct'
				? feedback.correct
				: outcome === 'partial'
					? (feedback.partial ?? feedback.incorrect)
					: feedback.incorrect
	};
}

export function evaluateInteraction(
	contract: LearnInteractionContract,
	response: unknown
): EvaluationResult {
	const feedback = contract.feedback;
	switch (contract.kind) {
		case 'choice':
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
				contract.config as { answers: string[] },
				response as { blanks: string[] },
				feedback
			);
		case 'numeric':
		case 'short-response':
			return evaluateNumeric(
				contract.config as { value: number; tolerance?: number },
				response as { value: number },
				feedback
			);
		case 'match-pairs':
		case 'classify':
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
		case 'image-hotspot':
			return evaluateChoice(
				contract.config as { correct_option_id: string },
				response as { selected_option_id: string },
				feedback
			);
		case 'drag-label':
			return evaluateMatchPairs(
				contract.config as { pairs: Array<{ left: string; right: string }> },
				response as { matches: Array<{ left: string; right: string }> },
				feedback
			);
		default: {
			const _exhaustive: never = contract.kind;
			return {
				outcome: 'incorrect',
				score_earned: 0,
				score_possible: 1,
				feedback: `Unsupported interaction kind: ${String(_exhaustive)}`
			};
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
			return result.score_possible > 0 && result.score_earned / result.score_possible >= rule.min_ratio;
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
	switch (contract.kind) {
		case 'choice':
		case 'image-hotspot':
			if (!contract.config.correct_option_id) errors.push('choice requires correct_option_id');
			break;
		case 'multi-select':
			if (!Array.isArray(contract.config.correct_option_ids)) {
				errors.push('multi-select requires correct_option_ids[]');
			}
			break;
		case 'fill-blank':
			if (!Array.isArray(contract.config.answers) || (contract.config.answers as unknown[]).length < 1) {
				errors.push('fill-blank requires answers[]');
			}
			break;
		case 'numeric':
		case 'short-response':
			if (typeof contract.config.value !== 'number') errors.push('numeric requires value:number');
			break;
		case 'match-pairs':
		case 'classify':
		case 'drag-label':
			if (!Array.isArray(contract.config.pairs)) errors.push('match-pairs requires pairs[]');
			break;
		case 'sequence':
			if (!Array.isArray(contract.config.order)) errors.push('sequence requires order[]');
			break;
	}
	return errors;
}

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
	const correctIndex = quiz.options.findIndex((o) => o.correct);
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
			correct_option_id: String(correctIndex >= 0 ? correctIndex : 0),
			options: quiz.options.map((o, i) => ({ id: String(i), text: o.text }))
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
	const answers = content.segments.filter((s) => s.is_blank).map((s) => s.answer ?? '');
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
		config: { answers },
		accessibility: {
			aria_label: content.instruction ?? 'Fill in the blank',
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
	const required = contracts.filter((c) => c.assessment_mode === 'graded');
	const completed = required.every((c) => states.find((s) => s.interaction_id === c.id)?.completed);
	return { completed, states, score_earned, score_possible };
}

export function asStringList(value: unknown): string[] {
	return asStringArray(value);
}

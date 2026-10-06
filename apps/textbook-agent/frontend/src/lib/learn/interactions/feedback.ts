import type { FeedbackSpec, InteractionRole } from './types';

const DEFAULT_FEEDBACK: FeedbackSpec = {
	correct: 'Correct',
	incorrect: 'Incorrect',
	partial: 'Partially correct'
};

const DEFAULT_PREDICTION_FEEDBACK = 'Prediction saved.';

export function normalizeFeedback(raw: unknown, role?: InteractionRole | null): FeedbackSpec {
	if (typeof raw === 'string' && raw.trim()) {
		return role === 'predict'
			? { ...DEFAULT_FEEDBACK, saved: raw }
			: { ...DEFAULT_FEEDBACK, correct: raw, incorrect: raw };
	}
	if (raw && typeof raw === 'object') {
		const obj = raw as Record<string, unknown>;
		const normalized: FeedbackSpec = {
			correct: typeof obj.correct === 'string' ? obj.correct : DEFAULT_FEEDBACK.correct,
			incorrect: typeof obj.incorrect === 'string' ? obj.incorrect : DEFAULT_FEEDBACK.incorrect,
			partial:
				typeof obj.partial === 'string'
					? obj.partial
					: typeof obj.incorrect === 'string'
					? obj.incorrect
					: DEFAULT_FEEDBACK.partial
		};
		if (role === 'predict') {
			normalized.saved = typeof obj.saved === 'string' ? obj.saved : DEFAULT_PREDICTION_FEEDBACK;
		}
		return normalized;
	}
	return role === 'predict'
		? { ...DEFAULT_FEEDBACK, saved: DEFAULT_PREDICTION_FEEDBACK }
		: { ...DEFAULT_FEEDBACK };
}

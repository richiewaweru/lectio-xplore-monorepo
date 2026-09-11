import type { FeedbackSpec } from './types';

const DEFAULT_FEEDBACK: FeedbackSpec = {
	correct: 'Correct',
	incorrect: 'Incorrect',
	partial: 'Partially correct'
};

export function normalizeFeedback(raw: unknown): FeedbackSpec {
	if (typeof raw === 'string' && raw.trim()) {
		return { ...DEFAULT_FEEDBACK, correct: raw, incorrect: raw };
	}
	if (raw && typeof raw === 'object') {
		const obj = raw as Record<string, unknown>;
		return {
			correct: typeof obj.correct === 'string' ? obj.correct : DEFAULT_FEEDBACK.correct,
			incorrect: typeof obj.incorrect === 'string' ? obj.incorrect : DEFAULT_FEEDBACK.incorrect,
			partial:
				typeof obj.partial === 'string'
					? obj.partial
					: typeof obj.incorrect === 'string'
						? obj.incorrect
						: DEFAULT_FEEDBACK.partial
		};
	}
	return { ...DEFAULT_FEEDBACK };
}

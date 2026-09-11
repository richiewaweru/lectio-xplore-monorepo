/**
 * Lightweight local evaluation for preview mode when no onSubmit bridge is provided.
 * Production uses the runtime API; these helpers mirror retained contract shapes.
 */

import type { FeedbackSpec, ServerEvaluation } from './types';

function feedbackFor(
	outcome: 'correct' | 'incorrect' | 'partial',
	feedback: FeedbackSpec
): string {
	if (outcome === 'correct') return feedback.correct;
	if (outcome === 'partial') return feedback.partial ?? feedback.incorrect;
	return feedback.incorrect;
}

export function evalChoice(
	correctOptionId: string,
	selected: string,
	feedback: FeedbackSpec
): ServerEvaluation {
	const ok = selected === correctOptionId;
	return {
		outcome: ok ? 'correct' : 'incorrect',
		feedback: feedbackFor(ok ? 'correct' : 'incorrect', feedback),
		score_earned: ok ? 1 : 0,
		score_possible: 1
	};
}

export function evalMultiSelect(
	correctIds: string[],
	selected: string[],
	feedback: FeedbackSpec
): ServerEvaluation {
	const correct = new Set(correctIds);
	const picked = new Set(selected);
	const allCorrect = [...correct].every((id) => picked.has(id));
	const noExtras = [...picked].every((id) => correct.has(id));
	const any = [...picked].some((id) => correct.has(id));
	const outcome =
		allCorrect && noExtras ? 'correct' : any ? 'partial' : 'incorrect';
	return {
		outcome,
		feedback: feedbackFor(outcome, feedback),
		score_earned: outcome === 'correct' ? 1 : outcome === 'partial' ? 0.5 : 0,
		score_possible: 1
	};
}

export function evalFillBlank(
	answers: string[],
	blanks: string[],
	feedback: FeedbackSpec,
	caseSensitive = false
): ServerEvaluation {
	const norm = (s: string) => (caseSensitive ? s.trim() : s.trim().toLowerCase());
	if (blanks.length !== answers.length) {
		return {
			outcome: 'incorrect',
			feedback: feedback.incorrect,
			score_earned: 0,
			score_possible: 1
		};
	}
	let hits = 0;
	for (let i = 0; i < answers.length; i++) {
		if (norm(blanks[i] ?? '') === norm(answers[i] ?? '')) hits += 1;
	}
	const outcome =
		hits === answers.length ? 'correct' : hits > 0 ? 'partial' : 'incorrect';
	return {
		outcome,
		feedback: feedbackFor(outcome, feedback),
		score_earned: answers.length ? hits / answers.length : 0,
		score_possible: 1
	};
}

export function evalNumeric(
	expected: number,
	tolerance: number,
	value: number,
	feedback: FeedbackSpec
): ServerEvaluation {
	const ok = Number.isFinite(value) && Math.abs(value - expected) <= tolerance;
	return {
		outcome: ok ? 'correct' : 'incorrect',
		feedback: feedbackFor(ok ? 'correct' : 'incorrect', feedback),
		score_earned: ok ? 1 : 0,
		score_possible: 1
	};
}

export function evalShortResponse(
	accepted: string[],
	raw: string,
	feedback: FeedbackSpec
): ServerEvaluation {
	const ok =
		accepted.length === 0
			? raw.trim().length > 0
			: accepted.some((a) => a.trim().toLowerCase() === raw.trim().toLowerCase());
	return {
		outcome: ok ? 'correct' : 'incorrect',
		feedback: feedbackFor(ok ? 'correct' : 'incorrect', feedback),
		score_earned: ok ? 1 : 0,
		score_possible: 1
	};
}

export function evalPairs(
	correct: Array<{ left: string; right: string }>,
	matches: Array<{ left: string; right: string }>,
	feedback: FeedbackSpec
): ServerEvaluation {
	const key = (p: { left: string; right: string }) => `${p.left}→${p.right}`;
	const want = new Set(correct.map(key));
	const got = new Set(matches.map(key));
	let hits = 0;
	for (const k of got) if (want.has(k)) hits += 1;
	const outcome =
		hits === want.size && got.size === want.size
			? 'correct'
			: hits > 0
				? 'partial'
				: 'incorrect';
	return {
		outcome,
		feedback: feedbackFor(outcome, feedback),
		score_earned: want.size ? hits / want.size : 0,
		score_possible: 1
	};
}

export function evalSequence(
	correctOrder: string[],
	order: string[],
	feedback: FeedbackSpec
): ServerEvaluation {
	const ok =
		correctOrder.length === order.length &&
		correctOrder.every((id, i) => id === order[i]);
	return {
		outcome: ok ? 'correct' : 'incorrect',
		feedback: feedbackFor(ok ? 'correct' : 'incorrect', feedback),
		score_earned: ok ? 1 : 0,
		score_possible: 1
	};
}

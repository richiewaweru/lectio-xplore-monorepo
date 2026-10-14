/**
 * Local evaluation for teacher preview when no onSubmit bridge is provided.
 * Production uses the runtime API; these helpers mirror its scoring, item_results
 * and retry rules (see attempt-rules.ts) so preview behaves like the learner view.
 */

import type { InteractionNode } from '$lib/learn/document/types';
import { attemptState, isTeacherReview, isUnmarked } from './attempt-rules';
import type { FeedbackSpec, ItemResults, LearnerResponse, ServerEvaluation } from './types';

/** Prediction submissions are recorded but never receive a right/wrong result. */
export function savePrediction(feedback: FeedbackSpec): ServerEvaluation {
	return { outcome: 'pending-review', feedback: feedback.saved ?? 'Prediction saved.' };
}

function feedbackFor(
	outcome: 'correct' | 'incorrect' | 'partial',
	feedback: FeedbackSpec
): string {
	if (outcome === 'correct') return feedback.correct;
	if (outcome === 'partial') return feedback.partial ?? feedback.incorrect;
	return feedback.incorrect;
}

function partialOutcome(earned: number, possible: number): 'correct' | 'partial' | 'incorrect' {
	if (possible > 0 && earned === possible) return 'correct';
	return earned > 0 ? 'partial' : 'incorrect';
}

function binary(ok: boolean, feedback: FeedbackSpec, itemResults: ItemResults): ServerEvaluation {
	return {
		outcome: ok ? 'correct' : 'incorrect',
		feedback: feedbackFor(ok ? 'correct' : 'incorrect', feedback),
		score_earned: ok ? 1 : 0,
		score_possible: 1,
		item_results: itemResults
	};
}

export function evalChoice(
	correctOptionId: string,
	selected: string,
	feedback: FeedbackSpec
): ServerEvaluation {
	const ok = selected === correctOptionId;
	return binary(ok, feedback, { [selected]: ok });
}

export function evalMultiSelect(
	correctIds: string[],
	selected: string[],
	feedback: FeedbackSpec,
	allOptionIds: string[] = []
): ServerEvaluation {
	const correct = new Set(correctIds);
	const picked = new Set(selected);
	const hits = [...picked].filter((id) => correct.has(id)).length;
	const falsePositives = picked.size - hits;
	const possible = correct.size;
	const earned = Math.max(0, hits - falsePositives);
	const outcome =
		earned === possible && falsePositives === 0 && picked.size === correct.size
			? 'correct'
			: earned > 0
				? 'partial'
				: 'incorrect';
	const ids = new Set([...allOptionIds, ...correct, ...picked]);
	const itemResults: Record<string, boolean> = {};
	for (const id of ids) itemResults[id] = picked.has(id) === correct.has(id);
	return {
		outcome,
		feedback: feedbackFor(outcome, feedback),
		score_earned: earned,
		score_possible: possible,
		item_results: itemResults
	};
}

/** answers[i] may be one string or a list of accepted alternatives. */
export function evalFillBlank(
	answers: Array<string | string[]>,
	blanks: string[],
	feedback: FeedbackSpec,
	caseSensitive = false
): ServerEvaluation {
	const norm = (s: string) => (caseSensitive ? s.trim() : s.trim().toLowerCase());
	const itemResults = answers.map((answer, i) => {
		const accepted = (Array.isArray(answer) ? answer : [answer]).map((a) => norm(String(a)));
		return accepted.includes(norm(blanks[i] ?? ''));
	});
	const hits = itemResults.filter(Boolean).length;
	const outcome = partialOutcome(hits, answers.length);
	return {
		outcome,
		feedback: feedbackFor(outcome, feedback),
		score_earned: hits,
		score_possible: answers.length,
		item_results: itemResults
	};
}

export function evalNumeric(
	expected: number,
	tolerance: number,
	value: number,
	feedback: FeedbackSpec
): ServerEvaluation {
	const ok = Number.isFinite(value) && Math.abs(value - expected) <= tolerance;
	return binary(ok, feedback, null);
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
	return binary(ok, feedback, null);
}

export function evalPairs(
	correct: Array<{ left: string; right: string }>,
	matches: Array<{ left: string; right: string }>,
	feedback: FeedbackSpec
): ServerEvaluation {
	const expected = new Map(correct.map((p) => [p.left, p.right]));
	const placed = new Map(matches.map((m) => [m.left, m.right]));
	let hits = 0;
	for (const m of matches) if (expected.get(m.left) === m.right) hits += 1;
	const itemResults: Record<string, boolean> = {};
	for (const [left, right] of expected) itemResults[left] = placed.get(left) === right;
	const outcome = partialOutcome(hits, expected.size);
	return {
		outcome,
		feedback: feedbackFor(outcome, feedback),
		score_earned: hits,
		score_possible: expected.size,
		item_results: itemResults
	};
}

export function evalSequence(
	correctOrder: string[],
	order: string[],
	feedback: FeedbackSpec
): ServerEvaluation {
	const itemResults = correctOrder.map((id, i) => order[i] === id);
	const hits = itemResults.filter(Boolean).length;
	const outcome = partialOutcome(hits, correctOrder.length);
	return {
		outcome,
		feedback: feedbackFor(outcome, feedback),
		score_earned: hits,
		score_possible: correctOrder.length,
		item_results: itemResults
	};
}

function strings(v: unknown): string[] {
	return Array.isArray(v) ? v.map(String) : [];
}

function optionIds(config: Record<string, unknown>): string[] {
	return Array.isArray(config.options)
		? (config.options as Array<{ id: unknown }>).map((o) => String(o.id))
		: [];
}

/** Mark one response against the preview config keys (no retry state). */
function markResponse(
	node: InteractionNode,
	response: LearnerResponse,
	feedback: FeedbackSpec
): ServerEvaluation {
	const c = (node.config ?? {}) as Record<string, unknown>;
	const pairs = Array.isArray(c.pairs)
		? (c.pairs as Array<{ left: unknown; right: unknown }>).map((p) => ({
				left: String(p.left),
				right: String(p.right)
			}))
		: [];
	switch (node.interaction_type) {
		case 'choice':
			return evalChoice(
				String(c.correct_option_id ?? ''),
				String(response.selected_option_id ?? ''),
				feedback
			);
		case 'multi-select':
			return evalMultiSelect(
				strings(c.correct_option_ids),
				strings(response.selected_option_ids),
				feedback,
				optionIds(c)
			);
		case 'fill-blank':
			return evalFillBlank(
				(Array.isArray(c.answers) ? c.answers : []) as Array<string | string[]>,
				strings(response.blanks),
				feedback,
				Boolean(c.case_sensitive)
			);
		case 'numeric':
			return evalNumeric(
				Number(c.value ?? 0),
				Number(c.tolerance ?? 0),
				Number(response.value),
				feedback
			);
		case 'short-response':
			return evalShortResponse(
				Array.isArray(c.answers) ? strings(c.answers) : strings(c.accepted_answers),
				String(response.text ?? ''),
				feedback
			);
		case 'match-pairs':
		case 'classify':
			return evalPairs(
				pairs,
				((response.matches as Array<{ left: unknown; right: unknown }>) ?? []).map((m) => ({
					left: String(m.left),
					right: String(m.right)
				})),
				feedback
			);
		case 'sequence': {
			const order = Array.isArray(c.order) ? strings(c.order) : strings(c.items);
			return evalSequence(order, strings(response.order), feedback);
		}
		default:
			return { outcome: 'incorrect', feedback: feedback.incorrect };
	}
}

/**
 * Preview attempt: mark `response` and attach attempts_used / attempts_left / reveal
 * following the server's rules. `priorOutcomes` are this question's earlier outcomes.
 */
export function evaluateLocalAttempt(
	node: InteractionNode,
	response: LearnerResponse,
	feedback: FeedbackSpec,
	priorOutcomes: string[]
): ServerEvaluation {
	let result: ServerEvaluation;
	if (isUnmarked(node)) {
		result = {
			outcome: 'pending-review',
			feedback: isTeacherReview(node)
				? (feedback.saved ?? 'Answer saved for your teacher to review.')
				: (feedback.saved ?? 'Prediction saved.')
		};
	} else {
		result = markResponse(node, response, feedback);
	}
	return { ...result, ...attemptState(node, [...priorOutcomes, result.outcome]) };
}

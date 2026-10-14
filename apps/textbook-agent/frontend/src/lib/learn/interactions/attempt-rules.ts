/**
 * Retry rules, mirrored from the backend (learn/runtime/attempt_rules.py).
 * Used ONLY by teacher preview, which has no server to count attempts.
 *
 * predict / teacher-review: 1 submission, no reveal.
 * check: 2 tries, reveal when out of tries and not correct.
 * practice: unlimited tries, reveal after 2 non-correct attempts.
 */
import type { InteractionNode } from '$lib/learn/document/types';
import type { InteractionRole, LearnerResponse } from './types';

type NodeLike = Pick<InteractionNode, 'interaction_type' | 'config' | 'role' | 'assessment_mode'>;

export function roleOf(node: NodeLike): InteractionRole {
	if (node.role === 'predict' || node.role === 'check' || node.role === 'practice') return node.role;
	return node.assessment_mode === 'graded' ? 'check' : 'practice';
}

export function isTeacherReview(node: NodeLike): boolean {
	const config = (node.config ?? {}) as Record<string, unknown>;
	return node.interaction_type === 'short-response' && config.evaluation === 'teacher-review';
}

/** True when a submission is recorded but never marked right/wrong. */
export function isUnmarked(node: NodeLike): boolean {
	return roleOf(node) === 'predict' || isTeacherReview(node);
}

function maxAttempts(node: NodeLike): number | null {
	if (isUnmarked(node)) return 1;
	return roleOf(node) === 'check' ? 2 : null;
}

export type AttemptState = {
	attempts_used: number;
	attempts_left: number | null;
	reveal: LearnerResponse | null;
};

/** attempts_used / attempts_left / reveal after the ordered outcomes. */
export function attemptState(node: NodeLike, outcomes: string[]): AttemptState {
	const used = outcomes.length;
	const max = maxAttempts(node);
	const last = outcomes[used - 1];
	let left: number | null = max === null ? null : Math.max(0, max - used);
	const role = roleOf(node);
	if (role !== 'practice' && last === 'correct') left = 0;
	if (isUnmarked(node)) left = 0;

	let reveal: LearnerResponse | null = null;
	if (!isUnmarked(node) && last !== undefined && last !== 'correct') {
		const nonCorrect = outcomes.filter((o) => o !== 'correct').length;
		const allowed = role === 'check' ? left === 0 : nonCorrect >= 2;
		if (allowed) reveal = revealFor(node);
	}
	return { attempts_used: used, attempts_left: left, reveal };
}

/** Correct answer in the learner response shape, from the preview config keys. */
export function revealFor(node: NodeLike): LearnerResponse | null {
	const c = (node.config ?? {}) as Record<string, unknown>;
	switch (node.interaction_type) {
		case 'choice':
			return c.correct_option_id ? { selected_option_id: String(c.correct_option_id) } : null;
		case 'multi-select':
			return Array.isArray(c.correct_option_ids) && c.correct_option_ids.length
				? { selected_option_ids: c.correct_option_ids.map(String) }
				: null;
		case 'fill-blank': {
			if (!Array.isArray(c.answers) || !c.answers.length) return null;
			return {
				blanks: c.answers.map((a) => String(Array.isArray(a) ? (a[0] ?? '') : a))
			};
		}
		case 'numeric':
			return typeof c.value === 'number' ? { value: c.value } : null;
		case 'short-response': {
			if (isTeacherReview(node)) return null;
			const accepted = Array.isArray(c.accepted_answers)
				? c.accepted_answers
				: Array.isArray(c.answers)
					? c.answers
					: [];
			return accepted.length ? { text: String(accepted[0]) } : null;
		}
		case 'match-pairs':
		case 'classify': {
			if (!Array.isArray(c.pairs) || !c.pairs.length) return null;
			return {
				matches: (c.pairs as Array<{ left: unknown; right: unknown }>).map((p) => ({
					left: String(p.left),
					right: String(p.right)
				}))
			};
		}
		case 'sequence':
			return Array.isArray(c.order) && c.order.length ? { order: c.order.map(String) } : null;
		default:
			return null;
	}
}

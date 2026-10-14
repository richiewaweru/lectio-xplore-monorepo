import { learnerFetch } from '$lib/learn/student/api/learner-fetch';
import { ensureOk } from '$lib/api/errors';
import type { ItemResults } from '$lib/learn/interactions/types';

export type AttemptSubmitRequest = {
	interaction_id: string;
	client_submission_id: string;
	response_json: Record<string, unknown>;
	section_id?: string;
	expected_release_id?: string;
};

export type AttemptSubmitResponse = {
	id: string;
	client_submission_id: string;
	interaction_id: string;
	outcome: string;
	score_earned: number;
	score_possible: number;
	feedback: string;
	completed: boolean;
	assessment_mode: string;
	idempotent_replay: boolean;
	response_json: Record<string, unknown>;
	item_results?: ItemResults;
	attempts_used?: number;
	attempts_left?: number | null;
	reveal?: Record<string, unknown> | null;
};

/** Latest-attempt state the server sends per interaction on GET /instances/{id}. */
export type InteractionStateDto = {
	attempts_used?: number;
	attempts_left?: number | null;
	reveal?: Record<string, unknown> | null;
	item_results?: ItemResults;
	outcome?: string;
	feedback?: string | null;
};

export type StoredAttempt = {
	id: string;
	interaction_id: string;
	client_submission_id: string;
	section_id?: string | null;
	outcome: string;
	feedback?: string | null;
	assessment_mode: string;
	score_earned: number;
	score_possible: number;
	response_json: Record<string, unknown>;
	created_at?: string | null;
	/** Attached by latestAttemptByInteraction from instance.interaction_states. */
	state?: InteractionStateDto;
};

export async function submitInstanceAttempt(
	instanceId: string,
	body: AttemptSubmitRequest
): Promise<AttemptSubmitResponse> {
	const response = await learnerFetch(`/api/v1/learn/instances/${instanceId}/attempts`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body)
	});
	await ensureOk(response);
	return (await response.json()) as AttemptSubmitResponse;
}

export function latestAttemptByInteraction(
	attempts: StoredAttempt[],
	states: Record<string, InteractionStateDto> = {}
): Map<string, StoredAttempt> {
	const map = new Map<string, StoredAttempt>();
	for (const attempt of attempts) {
		map.set(attempt.interaction_id, attempt);
	}
	for (const [id, attempt] of map) {
		if (states[id]) map.set(id, { ...attempt, state: states[id] });
	}
	return map;
}

export function newSubmissionId(prefix = 'sub'): string {
	if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
		return `${prefix}-${crypto.randomUUID()}`;
	}
	return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

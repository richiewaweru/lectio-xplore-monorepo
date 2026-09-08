import { apiFetch } from '$lib/api/client';
import { ensureOk } from '$lib/api/errors';

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
};

export type StoredAttempt = {
	id: string;
	interaction_id: string;
	client_submission_id: string;
	section_id?: string | null;
	outcome: string;
	assessment_mode: string;
	score_earned: number;
	score_possible: number;
	response_json: Record<string, unknown>;
	created_at?: string | null;
};

function learnerHeaders(extra: Record<string, string> = {}): Record<string, string> {
	const headers: Record<string, string> = { ...extra };
	if (typeof localStorage !== 'undefined') {
		const token = localStorage.getItem('x-learner-session');
		if (token) headers['X-Learner-Session'] = token;
	}
	return headers;
}

export async function submitInstanceAttempt(
	instanceId: string,
	body: AttemptSubmitRequest
): Promise<AttemptSubmitResponse> {
	const response = await apiFetch(`/api/v1/learn/instances/${instanceId}/attempts`, {
		method: 'POST',
		headers: learnerHeaders({ 'Content-Type': 'application/json' }),
		body: JSON.stringify(body)
	});
	await ensureOk(response);
	return (await response.json()) as AttemptSubmitResponse;
}

export function latestAttemptByInteraction(
	attempts: StoredAttempt[]
): Map<string, StoredAttempt> {
	const map = new Map<string, StoredAttempt>();
	for (const attempt of attempts) {
		map.set(attempt.interaction_id, attempt);
	}
	return map;
}

export function newSubmissionId(prefix = 'sub'): string {
	if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
		return `${prefix}-${crypto.randomUUID()}`;
	}
	return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

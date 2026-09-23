import { get } from 'svelte/store';

import { ensureOk } from '$lib/api/errors';
import { apiFetch } from '$lib/api/client';
import { authToken } from '$lib/shared/stores/auth';
import type { LessonApproachView } from '$lib/curriculum/lessons/teaching-plan-review';

function bearerHeaders(): Record<string, string> {
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	const token = get(authToken);
	if (token) headers.Authorization = `Bearer ${token}`;
	return headers;
}

export async function getLessonApproach(generationId: string): Promise<LessonApproachView> {
	const res = await apiFetch(
		`/api/v1/v3/generations/${encodeURIComponent(generationId)}/lesson-approach`,
		{ headers: bearerHeaders() }
	);
	await ensureOk(res, 'Could not load the lesson approach.');
	return res.json() as Promise<LessonApproachView>;
}

export async function approveLessonApproach(
	generationId: string,
	payload: {
		expected_revision: number;
		expected_content_hash: string;
		teacher_note?: string;
		path?: 'print' | 'learn';
	}
): Promise<Record<string, unknown>> {
	const pathQuery = payload.path ? `?path=${encodeURIComponent(payload.path)}` : '';
	const res = await apiFetch(
		`/api/v1/v3/generations/${encodeURIComponent(generationId)}/lesson-approach/approve${pathQuery}`,
		{
			method: 'POST',
			headers: bearerHeaders(),
			body: JSON.stringify({
				expected_revision: payload.expected_revision,
				expected_content_hash: payload.expected_content_hash,
				teacher_note: payload.teacher_note
			})
		}
	);
	await ensureOk(res, 'Could not approve the lesson approach.');
	return res.json() as Promise<Record<string, unknown>>;
}

export async function rejectLessonApproach(
	generationId: string,
	payload: { expected_revision: number; teacher_note?: string }
): Promise<Record<string, unknown>> {
	const res = await apiFetch(
		`/api/v1/v3/generations/${encodeURIComponent(generationId)}/lesson-approach/reject`,
		{
			method: 'POST',
			headers: bearerHeaders(),
			body: JSON.stringify(payload)
		}
	);
	await ensureOk(res, 'Could not reject the lesson approach.');
	return res.json() as Promise<Record<string, unknown>>;
}

import { get } from 'svelte/store';

import { ensureOk } from '$lib/api/errors';
import { apiFetch } from '$lib/api/client';
import { authToken } from '$lib/shared/stores/auth';
import type { V3ChunkedPlan, V3ChunkedPlanState, V3ChunkedStatus } from '$lib/types/v3';

function bearerHeaders(): Record<string, string> {
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	const token = get(authToken);
	if (token) headers.Authorization = `Bearer ${token}`;
	return headers;
}

export async function approveChunkedPlan(
	generationId: string,
	payload: { display_title?: string } = {}
): Promise<V3ChunkedPlanState> {
	const res = await apiFetch(`/api/v1/v3/chunked/${encodeURIComponent(generationId)}/approve`, {
		method: 'POST',
		headers: bearerHeaders(),
		body: JSON.stringify({ display_title: payload.display_title ?? null })
	});
	await ensureOk(res, 'Could not start section expansion.');
	return res.json() as Promise<V3ChunkedPlanState>;
}

export async function regenerateChunkedPlan(payload: {
	generation_id: string;
	note?: string;
}): Promise<V3ChunkedPlanState> {
	const res = await apiFetch(
		`/api/v1/v3/chunked/${encodeURIComponent(payload.generation_id)}/regenerate`,
		{
			method: 'POST',
			headers: bearerHeaders(),
			body: JSON.stringify({ note: payload.note ?? '' })
		}
	);
	await ensureOk(res, 'Could not regenerate the structural plan.');
	return res.json() as Promise<V3ChunkedPlanState>;
}

export async function getChunkedPlan(generationId: string): Promise<V3ChunkedPlan> {
	const res = await apiFetch(`/api/v1/v3/chunked/${encodeURIComponent(generationId)}/plan`, {
		method: 'GET',
		headers: bearerHeaders()
	});
	await ensureOk(res, 'Could not load the structural lesson plan.');
	return res.json() as Promise<V3ChunkedPlan>;
}

export async function getChunkedPlanStatus(generationId: string): Promise<V3ChunkedStatus> {
	const res = await apiFetch(`/api/v1/v3/chunked/${encodeURIComponent(generationId)}/status`, {
		method: 'GET',
		headers: bearerHeaders()
	});
	await ensureOk(res, 'Could not load chunked planning status.');
	return res.json() as Promise<V3ChunkedStatus>;
}

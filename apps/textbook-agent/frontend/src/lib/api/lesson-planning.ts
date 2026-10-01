import { get } from 'svelte/store';

import { ensureOk } from '$lib/api/errors';
import { apiFetch } from '$lib/api/client';
import { authToken } from '$lib/shared/stores/auth';
import type { PreparationStructure } from '$lib/types/v3';

function bearerHeaders(): Record<string, string> {
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	const token = get(authToken);
	if (token) headers.Authorization = `Bearer ${token}`;
	return headers;
}

/** Result of admitting (or re-reading) a preparation Run. */
export interface PreparationRunAdmission {
	generation_id: string;
	run_id: string;
	status: string;
	attempt: number;
	created: boolean;
	recovery_action: string | null;
}

/**
 * Approve the lesson structure and start planning (idempotent). Progress is
 * read from lesson-status `workspace.preparation`, never from this response.
 */
export async function startPreparationPlan(
	generationId: string,
	payload: { display_title?: string } = {}
): Promise<PreparationRunAdmission> {
	const res = await apiFetch(`/api/v1/preparations/${encodeURIComponent(generationId)}/plan`, {
		method: 'POST',
		headers: bearerHeaders(),
		body: JSON.stringify(payload.display_title ? { display_title: payload.display_title } : {})
	});
	await ensureOk(res, 'Could not start planning.');
	return res.json() as Promise<PreparationRunAdmission>;
}

/**
 * Admit the next bounded attempt for a failed or rejected plan. 409 codes
 * (PREPARATION_NOT_REGENERATABLE / _ATTEMPTS_EXHAUSTED / _NO_RUN) surface as
 * ApiError messages.
 */
export async function regeneratePreparationPlan(
	generationId: string
): Promise<PreparationRunAdmission> {
	const res = await apiFetch(
		`/api/v1/preparations/${encodeURIComponent(generationId)}/plan:regenerate`,
		{ method: 'POST', headers: bearerHeaders() }
	);
	await ensureOk(res, 'Could not regenerate the plan.');
	return res.json() as Promise<PreparationRunAdmission>;
}

/** Reopen the failed cards/plan of a preparation Run via the shared runtime. */
export async function retryPreparationRun(
	runId: string,
	failedWorkItemIds: string[]
): Promise<void> {
	const res = await apiFetch(`/api/v1/generation/runs/${encodeURIComponent(runId)}/retry`, {
		method: 'POST',
		headers: bearerHeaders(),
		body: JSON.stringify({ work_item_ids: failedWorkItemIds })
	});
	await ensureOk(res, 'Could not retry the failed plan steps.');
}

/** Structural plan preview shown during the stage-1 structural review. */
export async function getPreparationStructure(generationId: string): Promise<PreparationStructure> {
	const res = await apiFetch(`/api/v1/preparations/${encodeURIComponent(generationId)}/structure`, {
		method: 'GET',
		headers: bearerHeaders()
	});
	await ensureOk(res, 'Could not load the structural lesson plan.');
	return res.json() as Promise<PreparationStructure>;
}

import { apiFetch } from './client';
import { ensureOk } from './errors';
import type { PackStatusResponse } from '$lib/types/learning-pack';

export async function getPackStatus(packId: string): Promise<PackStatusResponse> {
	const response = await apiFetch(`/api/v1/packs/${encodeURIComponent(packId)}`);
	await ensureOk(response, 'Failed to load pack status.');
	return response.json();
}

export async function getPacks(limit = 20): Promise<PackStatusResponse[]> {
	const response = await apiFetch(`/api/v1/packs?limit=${limit}`);
	await ensureOk(response, 'Failed to load packs.');
	return response.json();
}

import { apiFetch } from './client';
import { ensureOk } from './errors';

export interface Capabilities {
	xplore_v2: boolean;
}

export async function getCapabilities(): Promise<Capabilities> {
	const response = await apiFetch('/api/v1/capabilities');
	await ensureOk(response, 'Could not load product capabilities.');
	return response.json();
}

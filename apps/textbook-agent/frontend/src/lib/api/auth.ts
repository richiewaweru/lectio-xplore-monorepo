import type { AuthResponse, User } from '$lib/types';
import { ensureOk } from './errors';
import { apiFetch } from './client';

export async function exchangeGoogleToken(credential: string): Promise<AuthResponse> {
	const response = await apiFetch('/api/v1/auth/google', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ credential })
	});
	await ensureOk(response, 'Authentication failed.');
	return response.json();
}

export async function fetchCurrentUser(): Promise<User> {
	const response = await apiFetch('/api/v1/auth/me');
	await ensureOk(response, 'Failed to fetch user.');
	return response.json();
}

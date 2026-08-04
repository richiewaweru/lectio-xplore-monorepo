import type { TeacherProfile, TeacherProfileUpsertRequest } from '$lib/types';
import { ensureOk } from './errors';
import { apiFetch } from './client';

export async function getProfile(): Promise<TeacherProfile> {
	const response = await apiFetch('/api/v1/profile');
	await ensureOk(response, 'Failed to fetch profile.');
	return response.json();
}

export async function createProfile(data: TeacherProfileUpsertRequest): Promise<TeacherProfile> {
	const response = await apiFetch('/api/v1/profile', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});
	await ensureOk(response, 'Failed to create profile.');
	return response.json();
}

export async function updateProfile(
	data: Partial<TeacherProfileUpsertRequest>
): Promise<TeacherProfile> {
	const response = await apiFetch('/api/v1/profile', {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});
	await ensureOk(response, 'Failed to update profile.');
	return response.json();
}

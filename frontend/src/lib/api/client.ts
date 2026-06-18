import { get } from 'svelte/store';
import { authToken } from '$lib/stores/auth';
import { resolveClientApiBase, type ApiEnvironment } from './config';

const API_BASE = resolveClientApiBase(import.meta.env as ApiEnvironment);

export function buildApiUrl(path: string): string {
	return API_BASE ? `${API_BASE}${path}` : path;
}

export function apiFetch(path: string, init?: RequestInit): Promise<Response> {
	const token = getAuthToken();
	const headers = new Headers(init?.headers);
	if (token) {
		headers.set('Authorization', `Bearer ${token}`);
	}
	return fetch(buildApiUrl(path), { ...init, headers });
}

export async function healthCheck(): Promise<{ status: string; version: string }> {
	const response = await fetch(buildApiUrl('/health'));
	return response.json();
}

function getAuthToken(): string | null {
	return get(authToken) ?? getQueryToken();
}

function getQueryToken(): string | null {
	if (typeof window === 'undefined') {
		return null;
	}
	return new URL(window.location.href).searchParams.get('token');
}

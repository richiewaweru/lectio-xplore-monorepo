import { beforeEach, describe, expect, it, vi } from 'vitest';

const { authTokenMock, fetchMock } = vi.hoisted(() => ({
	authTokenMock: { subscribe: vi.fn() },
	fetchMock: vi.fn()
}));

vi.mock('svelte/store', () => ({ get: vi.fn(() => 'stored-token') }));
vi.mock('$lib/stores/auth', () => ({ authToken: authTokenMock }));
vi.stubGlobal('fetch', fetchMock);

import { apiFetch } from './client';

describe('apiFetch authorization precedence', () => {
	beforeEach(() => fetchMock.mockReset());

	it('preserves an explicit token for tokenized print links', async () => {
		fetchMock.mockResolvedValue(new Response('{}', { status: 200 }));

		await apiFetch('/api/v1/v3/generations/g/document', {
			headers: { Authorization: 'Bearer explicit-token' }
		});

		const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
		expect(new Headers(init.headers).get('Authorization')).toBe('Bearer explicit-token');
	});

	it('falls back to the stored session token when none is supplied', async () => {
		fetchMock.mockResolvedValue(new Response('{}', { status: 200 }));

		await apiFetch('/api/v1/v3/generations/g/document');

		const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
		expect(new Headers(init.headers).get('Authorization')).toBe('Bearer stored-token');
	});
});

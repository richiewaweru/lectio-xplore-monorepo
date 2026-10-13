import { render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiFetch = vi.fn();
vi.mock('$lib/api/client', () => ({
	apiFetch: (...a: unknown[]) => apiFetch(...a),
	buildApiUrl: (p: string) => p
}));

import Page from './+page.svelte';

function res(status: number, body: unknown) {
	return {
		ok: status >= 200 && status < 300,
		status,
		headers: new Headers({ 'content-type': 'application/json' }),
		json: async () => body
	} as Response;
}

beforeEach(() => apiFetch.mockReset());

describe('interest list page', () => {
	it('renders rows', async () => {
		apiFetch.mockResolvedValueOnce(
			res(200, [
				{
					id: 'i1',
					display_name: 'Ann',
					email: 'a@b.co',
					phone: null,
					message: 'Teach me fractions',
					source: 'home',
					created_at: '2026-10-14T10:00:00'
				}
			])
		);
		render(Page);
		expect(await screen.findByText('Teach me fractions')).toBeTruthy();
		expect(screen.getByText('a@b.co')).toBeTruthy();
		expect(screen.getByText('Ann')).toBeTruthy();
		expect(apiFetch.mock.calls[0][0]).toContain('/api/v1/learn/interest');
	});

	it('shows an empty state', async () => {
		apiFetch.mockResolvedValueOnce(res(200, []));
		render(Page);
		expect(await screen.findByText('Nothing yet')).toBeTruthy();
	});

	it('shows an error when not authorised', async () => {
		apiFetch.mockResolvedValueOnce(res(401, { detail: 'Not authenticated' }));
		render(Page);
		expect(await screen.findByText(/Not authenticated/)).toBeTruthy();
	});
});

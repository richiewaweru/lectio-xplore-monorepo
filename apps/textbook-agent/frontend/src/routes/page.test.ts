// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import Layout from './+layout.svelte';

const { initializedStore, userStore, authedStore, goto, profileUser } = vi.hoisted(() => {
	function createStore<T>(initialValue: T) {
		let current = initialValue;
		const subscribers = new Set<(value: T) => void>();

		return {
			subscribe(callback: (value: T) => void) {
				subscribers.add(callback);
				callback(current);
				return () => subscribers.delete(callback);
			},
			set(value: T) {
				current = value;
				for (const callback of subscribers) {
					callback(current);
				}
			}
		};
	}

	const initializedStore = createStore(false);
	const userStore = createStore<{
		id: string;
		email: string;
		name: string;
		picture_url: string | null;
		has_profile: boolean;
		created_at: string;
		updated_at: string;
	} | null>(null);
	const authedStore = createStore(false);

	return {
		initializedStore,
		userStore,
		authedStore,
		goto: vi.fn(),
		profileUser: {
			id: 'user-1',
			email: 'teacher@example.com',
			name: 'Alex',
			picture_url: null,
			has_profile: true,
			created_at: '2026-04-06T00:00:00Z',
			updated_at: '2026-04-06T00:00:00Z'
		}
	};
});

vi.mock('$app/navigation', () => ({
	goto
}));

vi.mock('$app/state', () => ({
	page: {
		url: new URL('http://localhost/')
	}
}));

vi.mock('$lib/api/auth', () => ({
	fetchCurrentUser: vi.fn()
}));

vi.mock('$lib/stores/auth', () => ({
	authInitialized: initializedStore,
	authIsAuthenticated: authedStore,
	authUser: userStore,
	bootstrapAuth: vi.fn(async () => {
		userStore.set(profileUser);
		authedStore.set(true);
		initializedStore.set(true);
		return profileUser;
	}),
	logout: vi.fn()
}));

describe('root route session resume', () => {
	beforeEach(() => {
		initializedStore.set(false);
		userStore.set(null);
		authedStore.set(false);
		goto.mockReset();
	});

	afterEach(() => {
		cleanup();
		vi.clearAllMocks();
	});

	it('redirects a resumed authenticated session away from the root route', async () => {
		render(Layout, {
			props: {
				children: createRawSnippet(() => ({
					render: () => '<p>Redirecting...</p>'
				}))
			}
		});

		await waitFor(() =>
			expect(goto).toHaveBeenCalledWith('/units', { replaceState: true })
		);
		expect(screen.getByRole('link', { name: 'Lectio' }).getAttribute('href')).toBe('/units');
		expect(screen.getByRole('link', { name: 'Settings' }).getAttribute('href')).toBe('/settings');
		expect(screen.queryByRole('link', { name: 'Dashboard' })).toBeNull();
		expect(screen.queryByRole('link', { name: 'Builder' })).toBeNull();
		expect(screen.queryByText('⌘K')).toBeNull();
	});
});

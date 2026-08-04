// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { authStore } = vi.hoisted(() => {
	let current: unknown = null;
	const subscribers = new Set<(value: unknown) => void>();

	return {
		authStore: {
			subscribe(callback: (value: unknown) => void) {
				subscribers.add(callback);
				callback(current);
				return () => subscribers.delete(callback);
			},
			set(value: unknown) {
				current = value;
				for (const callback of subscribers) {
					callback(current);
				}
			}
		}
	};
});

vi.mock('$app/navigation', () => ({
	goto: vi.fn()
}));

vi.mock('$lib/api/auth', () => ({
	exchangeGoogleToken: vi.fn()
}));

vi.mock('$lib/api/errors', () => ({
	isApiError: () => false
}));

vi.mock('$lib/auth/google', () => ({
	mountGoogleSignIn: vi.fn()
}));

vi.mock('$lib/auth/routing', () => ({
	navigateToLanding: vi.fn()
}));

vi.mock('$lib/stores/auth', () => ({
	authUser: authStore,
	setAuth: vi.fn()
}));

import LoginPage from './+page.svelte';

describe('login page env guidance', () => {
	beforeEach(() => {
		authStore.set(null);
		vi.stubEnv('PUBLIC_GOOGLE_CLIENT_ID', '');
		vi.stubEnv('VITE_GOOGLE_CLIENT_ID', '');
	});

	afterEach(() => {
		cleanup();
		vi.unstubAllEnvs();
	});

	it('shows a clear missing-config message when the Google client id is missing', async () => {
		render(LoginPage);

		expect(await screen.findByText(/google sign-in is unavailable/i)).toBeTruthy();
		expect(
			await screen.findByText(/public_google_client_id\/vite_google_client_id/i)
		).toBeTruthy();
	});
});

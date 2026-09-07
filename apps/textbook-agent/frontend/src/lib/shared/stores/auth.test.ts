import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '$lib/api/errors';
import type { User } from '$lib/types';

import { bootstrapAuth, getToken, getUser, logout } from '$lib/stores/auth';

class MemoryStorage implements Storage {
	private store = new Map<string, string>();

	get length() {
		return this.store.size;
	}

	clear(): void {
		this.store.clear();
	}

	getItem(key: string): string | null {
		return this.store.get(key) ?? null;
	}

	key(index: number): string | null {
		return Array.from(this.store.keys())[index] ?? null;
	}

	removeItem(key: string): void {
		this.store.delete(key);
	}

	setItem(key: string, value: string): void {
		this.store.set(key, value);
	}
}

const TOKEN_KEY = 'textbook_agent_token';
const USER_KEY = 'textbook_agent_user';

const storedUser: User = {
	id: 'user-1',
	email: 'user@example.com',
	name: 'User',
	picture_url: null,
	has_profile: false,
	created_at: '2026-03-12T00:00:00Z',
	updated_at: '2026-03-12T00:00:00Z'
};

describe('auth bootstrap', () => {
	beforeEach(() => {
		vi.stubGlobal('localStorage', new MemoryStorage());
		logout();
	});

	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('keeps the user logged out when there is no stored token', async () => {
		const resolveCurrentUser = vi.fn();

		const result = await bootstrapAuth(resolveCurrentUser);

		expect(result).toBeNull();
		expect(resolveCurrentUser).not.toHaveBeenCalled();
		expect(getToken()).toBeNull();
		expect(getUser()).toBeNull();
	});

	it('replaces the stored user with the backend user on successful validation', async () => {
		localStorage.setItem(TOKEN_KEY, 'test-token');
		localStorage.setItem(USER_KEY, JSON.stringify(storedUser));

		const currentUser = { ...storedUser, has_profile: true };

		const result = await bootstrapAuth(vi.fn().mockResolvedValue(currentUser));

		expect(result).toEqual(currentUser);
		expect(getToken()).toBe('test-token');
		expect(getUser()).toEqual(currentUser);
		expect(localStorage.getItem(USER_KEY)).toBe(JSON.stringify(currentUser));
	});

	it('clears stored auth when the backend rejects the token', async () => {
		localStorage.setItem(TOKEN_KEY, 'expired-token');
		localStorage.setItem(USER_KEY, JSON.stringify(storedUser));

		await bootstrapAuth(
			vi.fn().mockRejectedValue(new ApiError(401, 'Invalid or expired token'))
		);

		expect(getToken()).toBeNull();
		expect(getUser()).toBeNull();
		expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
		expect(localStorage.getItem(USER_KEY)).toBeNull();
	});
});

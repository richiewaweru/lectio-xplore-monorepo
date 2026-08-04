import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('./client', () => ({
	apiFetch: vi.fn()
}));

vi.mock('./errors', () => ({
	ensureOk: vi.fn().mockResolvedValue(undefined)
}));

import { apiFetch } from './client';
import { updateProfile } from './profile';

describe('profile API helpers', () => {
	afterEach(() => {
		vi.clearAllMocks();
	});

	it('submits profile updates with PATCH for onboarding edit mode', async () => {
		vi.mocked(apiFetch).mockResolvedValue(
			new Response('{}', {
				status: 200,
				headers: { 'Content-Type': 'application/json' }
			})
		);

		await updateProfile({ teacher_role: 'tutor' });

		const apiFetchMock = vi.mocked(apiFetch);

		expect(apiFetch).toHaveBeenCalledTimes(1);
		expect(apiFetchMock.mock.calls[0][0]).toBe('/api/v1/profile');
		expect((apiFetchMock.mock.calls[0][1] as RequestInit).method).toBe('PATCH');
	});
});

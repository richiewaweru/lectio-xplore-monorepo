import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const apiFetch = vi.fn();
vi.mock('$lib/api/client', () => ({
	apiFetch: (...a: unknown[]) => apiFetch(...a),
	buildApiUrl: (p: string) => `http://api.test${p}`
}));

import { getStoredLearner, learnerFetch, storeLearner } from './learner-fetch';

function memoryStorage() {
	const m = new Map<string, string>();
	return {
		getItem: (k: string) => m.get(k) ?? null,
		setItem: (k: string, v: string) => void m.set(k, v),
		removeItem: (k: string) => void m.delete(k)
	};
}

describe('learnerFetch', () => {
	const fetchMock = vi.fn();
	beforeEach(() => {
		vi.stubGlobal('localStorage', memoryStorage());
		vi.stubGlobal('fetch', fetchMock);
		fetchMock.mockResolvedValue(new Response('{}'));
		apiFetch.mockResolvedValue(new Response('{}'));
	});
	afterEach(() => {
		vi.unstubAllGlobals();
		fetchMock.mockReset();
		apiFetch.mockReset();
	});

	it('sends the learner session and no Authorization header when a token exists', async () => {
		storeLearner({ token: 'tok', learnerId: 'l1', displayName: 'Aisha' });
		await learnerFetch('/api/v1/x', { headers: { Authorization: 'Bearer teacher', A: 'b' } });
		expect(apiFetch).not.toHaveBeenCalled();
		const [url, init] = fetchMock.mock.calls[0];
		expect(url).toBe('http://api.test/api/v1/x');
		const h = init.headers as Headers;
		expect(h.get('X-Learner-Session')).toBe('tok');
		expect(h.has('Authorization')).toBe(false);
		expect(h.get('A')).toBe('b');
	});

	it('falls back to apiFetch without a learner token', async () => {
		await learnerFetch('/api/v1/x', { method: 'POST' });
		expect(fetchMock).not.toHaveBeenCalled();
		expect(apiFetch).toHaveBeenCalledWith('/api/v1/x', { method: 'POST' });
	});

	it('reads the stored learner only when token and id exist', () => {
		expect(getStoredLearner()).toBeNull();
		storeLearner({ token: 'tok', learnerId: 'l1', displayName: 'Aisha' });
		expect(getStoredLearner()).toEqual({ token: 'tok', learnerId: 'l1', displayName: 'Aisha' });
	});
});

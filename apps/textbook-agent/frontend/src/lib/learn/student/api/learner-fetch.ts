import { apiFetch, buildApiUrl } from '$lib/api/client';

export const LEARNER_SESSION_KEY = 'x-learner-session';
export const LEARNER_ID_KEY = 'x-learner-id';
export const LEARNER_NAME_KEY = 'x-learner-name';
export const LEARNER_CODE_KEY = 'x-learner-code';

export type StoredLearner = { learnerId: string; displayName: string; token: string };

function readStorage(key: string): string | null {
	try {
		return typeof localStorage === 'undefined' ? null : localStorage.getItem(key);
	} catch {
		return null;
	}
}

export function getLearnerToken(): string | null {
	return readStorage(LEARNER_SESSION_KEY);
}

export function getStoredLearner(): StoredLearner | null {
	const token = readStorage(LEARNER_SESSION_KEY);
	const learnerId = readStorage(LEARNER_ID_KEY);
	if (!token || !learnerId) return null;
	return { token, learnerId, displayName: readStorage(LEARNER_NAME_KEY) ?? '' };
}

export function getStoredLearnerCode(): string | null {
	return readStorage(LEARNER_CODE_KEY);
}

export function storeLearner(input: {
	token: string;
	learnerId: string;
	displayName: string;
	code?: string;
}): void {
	try {
		if (input.code) localStorage.setItem(LEARNER_CODE_KEY, input.code);
		localStorage.setItem(LEARNER_SESSION_KEY, input.token);
		localStorage.setItem(LEARNER_ID_KEY, input.learnerId);
		localStorage.setItem(LEARNER_NAME_KEY, input.displayName);
	} catch {
		// Storage unavailable; the join still succeeds for this page view.
	}
}

/**
 * Fetch for student pages. With a learner session it sends only
 * X-Learner-Session (never a teacher Authorization header); without one it
 * falls back to apiFetch so a signed-in teacher previewing a lesson still works.
 */
export function learnerFetch(path: string, init?: RequestInit): Promise<Response> {
	const token = getLearnerToken();
	if (!token) return apiFetch(path, init);
	const headers = new Headers(init?.headers);
	headers.delete('Authorization');
	headers.set('X-Learner-Session', token);
	return fetch(buildApiUrl(path), { ...init, headers });
}

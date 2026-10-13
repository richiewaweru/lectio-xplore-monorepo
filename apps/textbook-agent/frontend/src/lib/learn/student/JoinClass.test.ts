import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const goto = vi.fn();
vi.mock('$app/navigation', () => ({ goto: (...a: unknown[]) => goto(...a) }));
vi.mock('$lib/api/client', () => ({
	apiFetch: vi.fn(),
	buildApiUrl: (p: string) => `http://api.test${p}`
}));

import JoinClass from './JoinClass.svelte';
import { LEARNER_CODE_KEY, LEARNER_ID_KEY, LEARNER_NAME_KEY, LEARNER_SESSION_KEY } from './api/learner-fetch';

function memoryStorage(seed: Record<string, string> = {}) {
	const m = new Map<string, string>(Object.entries(seed));
	return {
		getItem: (k: string) => m.get(k) ?? null,
		setItem: (k: string, v: string) => void m.set(k, v),
		removeItem: (k: string) => void m.delete(k),
		_m: m
	};
}

function jsonResponse(status: number, body: unknown) {
	return { ok: status >= 200 && status < 300, status, json: async () => body } as Response;
}

const fetchMock = vi.fn();

beforeEach(() => {
	goto.mockReset();
	fetchMock.mockReset();
	vi.stubGlobal('fetch', fetchMock);
	vi.stubGlobal('localStorage', memoryStorage());
});
afterEach(() => vi.unstubAllGlobals());

describe('JoinClass success screen', () => {
	it('shows the code, bookmark link and Start learning after joining', async () => {
		fetchMock.mockResolvedValueOnce(
			jsonResponse(200, { token: 't1', learner_id: 'L1', display_name: 'Aisha', code: 'HAPPY-TIGER-4821' })
		);
		render(JoinClass, { code: 'ABC123' });
		await fireEvent.input(screen.getByPlaceholderText('Aisha'), { target: { value: 'Aisha' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Join class' }));

		expect(await screen.findByText('Welcome, Aisha')).toBeTruthy();
		expect(screen.getByTestId('learner-code').textContent).toBe('HAPPY-TIGER-4821');
		expect(screen.getByText(/gets your progress back on any device/)).toBeTruthy();
		const link = screen.getByRole('link') as HTMLAnchorElement;
		expect(link.href).toBe(`${location.origin}/resume/HAPPY-TIGER-4821`);
		expect(localStorage.getItem(LEARNER_CODE_KEY)).toBe('HAPPY-TIGER-4821');
		expect(goto).not.toHaveBeenCalled();

		await fireEvent.click(screen.getByRole('button', { name: /Start learning/ }));
		expect(goto).toHaveBeenCalledWith('/learn/home/L1');
	});
});

describe('JoinClass code resume', () => {
	async function submitCode(value: string) {
		render(JoinClass, { code: '' });
		await fireEvent.input(screen.getByPlaceholderText('HAPPY-TIGER-4821'), { target: { value } });
		await fireEvent.click(screen.getAllByRole('button', { name: 'Continue' })[1]);
	}

	it('stores the learner and goes home on success', async () => {
		fetchMock.mockResolvedValueOnce(
			jsonResponse(200, { token: 't2', learner_id: 'L2', display_name: 'Ben', session_id: 's' })
		);
		await submitCode('happy tiger 4821');
		await waitFor(() => expect(goto).toHaveBeenCalledWith('/learn/home/L2'));
		const [url, init] = fetchMock.mock.calls[0];
		expect(url).toBe('http://api.test/api/v1/learn/learners/resume');
		expect(JSON.parse(init.body)).toEqual({ code: 'happy tiger 4821' });
		expect(localStorage.getItem(LEARNER_SESSION_KEY)).toBe('t2');
		expect(localStorage.getItem(LEARNER_ID_KEY)).toBe('L2');
		expect(localStorage.getItem(LEARNER_NAME_KEY)).toBe('Ben');
	});

	it('shows a generic message on 404', async () => {
		fetchMock.mockResolvedValueOnce(jsonResponse(404, { detail: 'That code was not found' }));
		await submitCode('NOPE-AAAA');
		expect(await screen.findByText(/couldn't find that code/)).toBeTruthy();
		expect(goto).not.toHaveBeenCalled();
	});

	it('shows a friendly message on 429', async () => {
		fetchMock.mockResolvedValueOnce(jsonResponse(429, {}));
		await submitCode('NOPE-AAAA');
		expect(await screen.findByText(/Too many tries/)).toBeTruthy();
	});
});

describe('JoinClass same device', () => {
	const seed = {
		[LEARNER_SESSION_KEY]: 'tok',
		[LEARNER_ID_KEY]: 'L9',
		[LEARNER_NAME_KEY]: 'Zed'
	};

	it('joins the class as the stored learner, then goes home', async () => {
		vi.stubGlobal('localStorage', memoryStorage(seed));
		fetchMock.mockResolvedValueOnce(jsonResponse(200, { learner_id: 'L9', class_id: 'c', class_name: 'X' }));
		render(JoinClass, { code: 'ABC123' });
		await fireEvent.click(await screen.findByRole('button', { name: 'Continue as Zed' }));
		await waitFor(() => expect(goto).toHaveBeenCalledWith('/learn/home/L9'));
		const [url, init] = fetchMock.mock.calls[0];
		expect(url).toBe('http://api.test/api/v1/learn/classes/join-existing');
		expect((init.headers as Headers).get('X-Learner-Session')).toBe('tok');
		expect(JSON.parse(init.body)).toEqual({ invite_code: 'ABC123' });
	});

	it('does not navigate when join-existing fails', async () => {
		vi.stubGlobal('localStorage', memoryStorage(seed));
		fetchMock.mockResolvedValueOnce(jsonResponse(404, { detail: 'Invite not found' }));
		render(JoinClass, { code: 'BAD' });
		await fireEvent.click(await screen.findByRole('button', { name: 'Continue as Zed' }));
		expect(await screen.findByText('Invite not found')).toBeTruthy();
		expect(goto).not.toHaveBeenCalled();
	});

	it('offers Not you? to join as someone else', async () => {
		vi.stubGlobal('localStorage', memoryStorage(seed));
		render(JoinClass, { code: 'ABC123' });
		await fireEvent.click(await screen.findByRole('button', { name: /Not you/ }));
		expect(screen.queryByRole('button', { name: 'Continue as Zed' })).toBeNull();
		expect(screen.getByPlaceholderText('Aisha')).toBeTruthy();
	});
});

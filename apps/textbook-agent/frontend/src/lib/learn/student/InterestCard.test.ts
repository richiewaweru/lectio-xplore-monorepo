import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const fetchMock = vi.hoisted(() => vi.fn());
vi.mock('$lib/api/client', () => ({
	apiFetch: (p: string, init?: RequestInit) => fetchMock(`http://api.test${p}`, init),
	buildApiUrl: (p: string) => `http://api.test${p}`
}));

import InterestCard from './InterestCard.svelte';

function res(status: number, body: unknown = { ok: true }) {
	return { ok: status >= 200 && status < 300, status, json: async () => body } as Response;
}

beforeEach(() => {
	fetchMock.mockReset();
	vi.stubGlobal('fetch', fetchMock);
	vi.stubGlobal('localStorage', {
		getItem: () => null,
		setItem: () => {},
		removeItem: () => {}
	});
});
afterEach(() => vi.unstubAllGlobals());

async function fill(message: string, email = '', phone = '') {
	await fireEvent.input(screen.getByLabelText("Tell me what you're curious about"), {
		target: { value: message }
	});
	if (email) await fireEvent.input(screen.getByLabelText('Email'), { target: { value: email } });
	if (phone) await fireEvent.input(screen.getByLabelText('Phone'), { target: { value: phone } });
}

describe('InterestCard', () => {
	it('requires a message', async () => {
		render(InterestCard, { source: 'home' });
		await fill('   ', 'a@b.co');
		await fireEvent.click(screen.getByRole('button', { name: 'Send' }));
		expect((await screen.findByRole('alert')).textContent).toMatch(/curious/);
		expect(fetchMock).not.toHaveBeenCalled();
	});

	it('requires an email or phone and checks the email shape', async () => {
		render(InterestCard, { source: 'home' });
		await fill('Hello');
		await fireEvent.click(screen.getByRole('button', { name: 'Send' }));
		expect((await screen.findByRole('alert')).textContent).toMatch(/email or a phone/);
		await fill('Hello', 'nope');
		await fireEvent.click(screen.getByRole('button', { name: 'Send' }));
		await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/email does not/));
		expect(fetchMock).not.toHaveBeenCalled();
	});

	it('posts with the source and shows thanks on success', async () => {
		fetchMock.mockResolvedValueOnce(res(200));
		render(InterestCard, { source: 'topic' });
		await fill('Fractions', '', '+254 700 123 456');
		await fireEvent.click(screen.getByRole('button', { name: 'Send' }));
		expect(await screen.findByText('Thank you')).toBeTruthy();
		const [url, init] = fetchMock.mock.calls[0];
		expect(url).toBe('http://api.test/api/v1/learn/interest');
		const body = JSON.parse(init.body);
		expect(body).toMatchObject({
			message: 'Fractions',
			email: null,
			phone: '+254 700 123 456',
			source: 'topic',
			website: ''
		});
	});

	it('shows a friendly message on 429', async () => {
		fetchMock.mockResolvedValueOnce(res(429, { detail: 'rate' }));
		render(InterestCard, { source: 'home' });
		await fill('Hi', 'a@b.co');
		await fireEvent.click(screen.getByRole('button', { name: 'Send' }));
		expect((await screen.findByRole('alert')).textContent).toMatch(/try again in a little while/);
		expect(screen.queryByText('Thank you')).toBeNull();
	});
});

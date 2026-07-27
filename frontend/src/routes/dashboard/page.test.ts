// @vitest-environment jsdom

import { cleanup, render, waitFor } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

const goto = vi.hoisted(() => vi.fn());

vi.mock('$app/navigation', () => ({ goto }));

import DashboardRedirect from './+page.svelte';

describe('/dashboard compatibility route', () => {
	afterEach(() => {
		cleanup();
		goto.mockReset();
	});

	it('replaces the legacy route with the lessons workspace', async () => {
		render(DashboardRedirect);
		await waitFor(() => expect(goto).toHaveBeenCalledWith('/lessons', { replaceState: true }));
	});
});

// @vitest-environment jsdom

import { cleanup, render, waitFor } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

const goto = vi.hoisted(() => vi.fn());
vi.mock('$app/navigation', () => ({ goto }));

import LessonsRedirect from './+page.svelte';

describe('/lessons historical route', () => {
	afterEach(() => {
		cleanup();
		goto.mockReset();
	});

	it('redirects to the canonical native units workspace', async () => {
		render(LessonsRedirect);
		await waitFor(() => expect(goto).toHaveBeenCalledWith('/units', { replaceState: true }));
	});
});

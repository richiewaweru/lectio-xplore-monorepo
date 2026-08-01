import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('./client', () => ({ apiFetch: vi.fn() }));
vi.mock('./errors', () => ({ ensureOk: vi.fn().mockResolvedValue(undefined) }));

import { apiFetch } from './client';
import { getCapabilities } from './capabilities';

describe('capability API helper', () => {
	afterEach(() => vi.clearAllMocks());

	it('loads server-controlled product capabilities', async () => {
		vi.mocked(apiFetch).mockResolvedValue(new Response(JSON.stringify({ xplore_v2: true })));

		await expect(getCapabilities()).resolves.toEqual({ xplore_v2: true });
		expect(apiFetch).toHaveBeenCalledWith('/api/v1/capabilities');
	});
});

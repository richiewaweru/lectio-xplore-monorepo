import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('./client', () => ({ apiFetch: vi.fn() }));
vi.mock('./errors', () => ({ ensureOk: vi.fn().mockResolvedValue(undefined) }));

import { apiFetch } from './client';
import { getPreparationStructure } from './lesson-planning';

describe('lesson planning API helpers', () => {
	afterEach(() => vi.clearAllMocks());

	it('reads the structural preview from the owned preparation endpoint', async () => {
		const payload = { generation_id: 'gen 1', structural_plan: { lesson_title: 'Plant water' } };
		vi.mocked(apiFetch).mockResolvedValue(
			new Response(JSON.stringify(payload), {
				status: 200,
				headers: { 'Content-Type': 'application/json' }
			})
		);

		const result = await getPreparationStructure('gen 1');

		expect(vi.mocked(apiFetch).mock.calls[0][0]).toBe('/api/v1/preparations/gen%201/structure');
		expect(vi.mocked(apiFetch).mock.calls[0][1]).toMatchObject({ method: 'GET' });
		expect(result).toEqual(payload);
	});
});

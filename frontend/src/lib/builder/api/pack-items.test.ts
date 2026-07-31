import { beforeEach, describe, expect, it, vi } from 'vitest';

const { apiFetchMock } = vi.hoisted(() => ({
	apiFetchMock: vi.fn()
}));

vi.mock('$lib/api/client', () => ({
	apiFetch: apiFetchMock
}));

vi.mock('$lib/api/errors', () => ({
	ensureOk: async (response: Response, message: string) => {
		if (!response.ok) throw new Error(message);
	}
}));

import { getPackItems, regenerateCardItems, updatePackItem } from './pack-items';

describe('pack item API', () => {
	beforeEach(() => {
		apiFetchMock.mockReset();
		apiFetchMock.mockResolvedValue(
			new Response(JSON.stringify([]), {
				status: 200,
				headers: { 'Content-Type': 'application/json' }
			})
		);
	});

	it('loads the pack-level shared item set', async () => {
		await getPackItems('pack one');

		expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/v3/packs/pack%20one/items');
	});

	it('saves a teacher-edited item', async () => {
		await updatePackItem('pack-1', {
			id: 'pack-1:card.i1',
			prompt_text: 'Revised prompt',
			options: [
				{
					key: 'a',
					text: 'Answer',
					correct: true,
					diagnoses: null,
					teacher_edited: false
				}
			]
		});

		const [, init] = apiFetchMock.mock.calls[0] as [string, RequestInit];
		expect(init.method).toBe('PATCH');
		expect(JSON.parse(String(init.body))).toMatchObject({
			prompt_text: 'Revised prompt'
		});
	});

	it('regenerates only one card item set', async () => {
		await regenerateCardItems('pack-1', 'card-1');

		expect(apiFetchMock).toHaveBeenCalledWith(
			'/api/v1/v3/packs/pack-1/cards/card-1/items/regenerate',
			{ method: 'POST' }
		);
	});
});

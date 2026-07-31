import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('./client', () => ({ apiFetch: vi.fn() }));
vi.mock('./errors', () => ({ ensureOk: vi.fn().mockResolvedValue(undefined) }));

import { apiFetch } from './client';
import { planUnitPath, preparePathLesson, previewSkeleton } from './units';

function ok(payload: unknown): Response {
	return new Response(JSON.stringify(payload), {
		status: 200,
		headers: { 'Content-Type': 'application/json' }
	});
}

describe('unit API helpers', () => {
	afterEach(() => vi.clearAllMocks());

	it('plans from persisted scope without count or duration targets', async () => {
		vi.mocked(apiFetch).mockResolvedValue(ok({ lessons: [] }));
		await planUnitPath('unit 1', {
			topic: 'Photosynthesis',
			subject: 'Science',
			grade_level: 'Grade 7',
			destination_objective: 'Explain photosynthesis.',
			starting_knowledge: ['Plants are living things.']
		});

		const [path, init] = vi.mocked(apiFetch).mock.calls[0];
		expect(path).toBe('/api/v1/units/unit%201/path:plan');
		const body = JSON.parse(String((init as RequestInit).body));
		expect(body.lesson_count).toBeUndefined();
		expect(body.duration_minutes).toBeUndefined();
	});

	it('prepares the core path lesson through the explicit bridge', async () => {
		vi.mocked(apiFetch).mockResolvedValue(ok({ generation_id: 'generation-1' }));
		await preparePathLesson('unit-1', 'lesson-1', 'first_exposure');

		expect(apiFetch).toHaveBeenCalledWith(
			'/api/v1/units/unit-1/path/lessons/lesson-1:prepare',
			expect.objectContaining({
				method: 'POST',
				body: JSON.stringify({ group_ids: [], lesson_mode: 'first_exposure' })
			})
		);
	});

	it('previews all three declared group shapes without a generation call', async () => {
		vi.mocked(apiFetch).mockResolvedValue(ok({ variants: [] }));
		await previewSkeleton('Explain photosynthesis.', 'first_exposure');

		const [, init] = vi.mocked(apiFetch).mock.calls[0];
		expect(JSON.parse(String((init as RequestInit).body)).group_profiles).toEqual([
			'support',
			'core',
			'extension'
		]);
	});
});

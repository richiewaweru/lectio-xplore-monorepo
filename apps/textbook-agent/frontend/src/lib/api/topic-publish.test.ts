import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiFetch = vi.hoisted(() => vi.fn());
vi.mock('$lib/api/client', () => ({ apiFetch }));

import { assignReleaseToClass, ReleaseNotLinkedError, getPublishCandidates } from './topic-publish';

function json(status: number, body: unknown): Response {
	return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
}

describe('topic-publish client', () => {
	beforeEach(() => apiFetch.mockReset());

	it('sends require_path_lesson_id when assigning', async () => {
		apiFetch.mockResolvedValue(json(200, {}));
		await assignReleaseToClass({ learn_release_id: 'r1', title: 'T', class_id: 'c1', mode: 'rolling' });
		const [, init] = apiFetch.mock.calls[0];
		expect(JSON.parse(init.body)).toMatchObject({ learn_release_id: 'r1', class_ids: ['c1'], require_path_lesson_id: true });
	});

	it('maps RELEASE_NOT_LINKED_TO_PATH_LESSON 422 to ReleaseNotLinkedError', async () => {
		apiFetch.mockResolvedValue(json(422, { detail: { code: 'RELEASE_NOT_LINKED_TO_PATH_LESSON', message: 'x' } }));
		await expect(
			assignReleaseToClass({ learn_release_id: 'r1', title: 'T', class_id: 'c1', mode: 'rolling' })
		).rejects.toBeInstanceOf(ReleaseNotLinkedError);
	});

	it('passes class_id to publish-candidates', async () => {
		apiFetch.mockResolvedValue(json(200, { unit_id: 'u', unit_title: 'U', class_id: 'c 1', lessons: [] }));
		await getPublishCandidates('u1', 'c 1');
		expect(apiFetch).toHaveBeenCalledWith('/api/v1/units/u1/publish-candidates?class_id=c%201');
	});
});

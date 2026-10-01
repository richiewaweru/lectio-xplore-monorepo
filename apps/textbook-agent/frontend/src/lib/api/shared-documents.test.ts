import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('./client', () => ({ apiFetch: vi.fn() }));
vi.mock('./errors', () => ({ ensureOk: vi.fn().mockResolvedValue(undefined) }));

import { apiFetch } from './client';
import { getReviewDraft, saveReviewDraftRevision, submitReviewDraft } from './shared-documents';

function ok(payload: unknown): Response {
	return new Response(JSON.stringify(payload), {
		status: 200,
		headers: { 'Content-Type': 'application/json' }
	});
}

describe('shared-documents API helpers', () => {
	afterEach(() => vi.clearAllMocks());

	it('loads the review draft for a run', async () => {
		vi.mocked(apiFetch).mockResolvedValue(ok({ status: 'draft', draft: {}, document: {}, issues: [] }));
		await getReviewDraft('run-1');
		expect(apiFetch).toHaveBeenCalledWith(
			'/api/v1/shared-documents/runs/run-1/review-draft',
			undefined
		);
	});

	it('encodes the run id when saving a revision', async () => {
		vi.mocked(apiFetch).mockResolvedValue(ok({ status: 'draft', draft: {}, document: {}, issues: [] }));
		await saveReviewDraftRevision('run 1', {
			expected_revision: 3,
			expected_hash: 'a'.repeat(64),
			edits: [{ section_id: 's1', node_id: 'n1', field: 'text', value: 'Fixed text' }]
		});

		const [path, init] = vi.mocked(apiFetch).mock.calls[0];
		expect(path).toBe('/api/v1/shared-documents/runs/run%201/review-draft/revisions');
		expect((init as RequestInit).method).toBe('POST');
		const body = JSON.parse(String((init as RequestInit).body));
		expect(body).toEqual({
			expected_revision: 3,
			expected_hash: 'a'.repeat(64),
			edits: [{ section_id: 's1', node_id: 'n1', field: 'text', value: 'Fixed text' }]
		});
	});

	it('submits the draft for re-qualification', async () => {
		vi.mocked(apiFetch).mockResolvedValue(
			ok({ run_id: 'run-1', document_id: 'doc-1', document_revision: 4, work_item_id: 'wi-1' })
		);
		await submitReviewDraft('run-1', { expected_revision: 4, expected_hash: 'b'.repeat(64) });

		const [path, init] = vi.mocked(apiFetch).mock.calls[0];
		expect(path).toBe('/api/v1/shared-documents/runs/run-1/review-draft/submit');
		expect((init as RequestInit).method).toBe('POST');
		expect(JSON.parse(String((init as RequestInit).body))).toEqual({
			expected_revision: 4,
			expected_hash: 'b'.repeat(64)
		});
	});
});

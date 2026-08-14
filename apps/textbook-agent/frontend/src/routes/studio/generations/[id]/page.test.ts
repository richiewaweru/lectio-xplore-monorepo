// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const pageDocumentV2Fixture = JSON.parse(
	readFileSync(
		join(process.cwd(), '..', 'backend', 'tests', 'fixtures', 'lectio-page', 'valid-document.json'),
		'utf8'
	)
);

const {
	pageState,
	getV3GenerationDetail,
	fetchV3Document,
	downloadV3GenerationPdf,
	retryNativeVisuals
} = vi.hoisted(() => ({
	pageState: {
		params: { id: 'gen-123' },
		url: new URL('http://localhost/studio/generations/gen-123')
	},
	getV3GenerationDetail: vi.fn(),
	fetchV3Document: vi.fn(),
	downloadV3GenerationPdf: vi.fn(),
	retryNativeVisuals: vi.fn()
}));

vi.mock('$app/state', () => ({
	page: pageState
}));

vi.mock('$lib/api/v3', () => ({
	getV3GenerationDetail,
	fetchV3Document,
	downloadV3GenerationPdf,
	retryNativeVisuals
}));

vi.mock('$lib/components/studio/V3BookletPackView.svelte', async () => ({
	default: (await import('./__fixtures__/MockV3BookletPackView.svelte')).default
}));

import CompletedV3GenerationPage from './+page.svelte';

describe('completed V3 generation page', () => {
	beforeEach(() => {
		getV3GenerationDetail.mockReset();
		fetchV3Document.mockReset();
		downloadV3GenerationPdf.mockReset();
		retryNativeVisuals.mockReset();

		getV3GenerationDetail.mockResolvedValue({
			id: 'gen-123',
			subject: 'Mathematics',
			title: 'Quadratic review',
			status: 'completed',
			booklet_status: 'final_ready',
			template_id: 'guided-concept-path',
			section_count: 1,
			document_section_count: 1,
			report_json: {},
			created_at: '2026-05-01T00:00:00Z',
			completed_at: '2026-05-01T00:05:00Z'
		});
		fetchV3Document.mockResolvedValue({
			kind: 'v3_booklet_pack',
			generation_id: 'gen-123',
			template_id: 'guided-concept-path',
			status: 'final_ready',
			subject: 'Mathematics',
			sections: [{ section_id: 's-1', header: { title: 'Intro' } }],
			warnings: [],
			section_diagnostics: [],
			booklet_issues: []
		});
	});

	afterEach(() => {
		cleanup();
	});

	it('loads V3 detail + V3 document and renders the pack without stream dependencies', async () => {
		render(CompletedV3GenerationPage);

		await waitFor(() => expect(getV3GenerationDetail).toHaveBeenCalledWith('gen-123'));
		await waitFor(() => expect(fetchV3Document).toHaveBeenCalledWith('gen-123'));
		expect(await screen.findByText(/Quadratic review/i)).toBeTruthy();
		expect(await screen.findByTestId('v3-pack-view')).toBeTruthy();
		expect(screen.queryByText(/loading v3 generation/i)).toBeNull();
	});

	it('shows parent lesson link for supplement generations', async () => {
		getV3GenerationDetail.mockResolvedValueOnce({
			id: 'gen-123',
			subject: 'Mathematics',
			title: 'Exit ticket',
			status: 'completed',
			booklet_status: 'final_ready',
			template_id: 'guided-concept-path',
			section_count: 1,
			document_section_count: 1,
			report_json: {},
			blueprint_id: 'bp-child',
			planning_artifact: {
				source: {
					kind: 'supplement',
					parent_generation_id: 'gen-parent',
					parent_blueprint_id: 'bp-parent',
					target_resource_type: 'exit_ticket'
				}
			},
			created_at: '2026-05-01T00:00:00Z',
			completed_at: '2026-05-01T00:05:00Z'
		});
		fetchV3Document.mockResolvedValueOnce({
			kind: 'v3_booklet_pack',
			generation_id: 'gen-123',
			template_id: 'guided-concept-path',
			status: 'final_ready',
			subject: 'Mathematics',
			sections: [{ section_id: 's-1', header: { title: 'Intro' } }],
			warnings: [],
			section_diagnostics: [],
			booklet_issues: []
		});

		render(CompletedV3GenerationPage);

		const parentLink = await screen.findByRole('link', { name: /parent lesson/i });
		expect(parentLink.getAttribute('href')).toBe('/studio/generations/gen-parent');
		expect(await screen.findByText(/Companion resource based on/i)).toBeTruthy();
	});

	it('shows an error when the V3 document cannot be coerced to a renderable pack', async () => {
		fetchV3Document.mockResolvedValueOnce({
			kind: 'v3_booklet_pack',
			sections: []
		});

		render(CompletedV3GenerationPage);

		expect(await screen.findByText(/Document is not renderable yet\./i)).toBeTruthy();
	});

	it('enables final PDF export for a completed V2 page document', async () => {
		fetchV3Document.mockResolvedValueOnce(pageDocumentV2Fixture);

		render(CompletedV3GenerationPage);

		expect(await screen.findByRole('button', { name: 'Download Final PDF' })).not.toHaveProperty(
			'disabled',
			true
		);
	});

	it('fails closed instead of falling back to V3 when a native V2 document is malformed', async () => {
		getV3GenerationDetail.mockResolvedValueOnce({
			id: 'gen-123',
			subject: 'Science',
			title: 'Native lesson',
			status: 'ready',
			booklet_status: 'final_ready',
			template_id: 'guided-concept-path',
			section_count: 1,
			document_section_count: 1,
			report_json: {},
			native_whole_lesson: true,
			document_contract_version: 2,
			created_at: null,
			completed_at: null
		});
		fetchV3Document.mockResolvedValueOnce({ document_version: 2, lectio_document: { title: 'Missing sections' } });

		render(CompletedV3GenerationPage);

		expect(await screen.findByText(/Native document contract error/i)).toBeTruthy();
		expect(screen.queryByTestId('v3-pack-view')).toBeNull();
	});

	it('shows a visual-quality retry only for a ready generation with flagged visuals', async () => {
		const flaggedDetail = {
			id: 'gen-123',
			subject: 'Science',
			title: 'Water cycle',
			status: 'ready',
			booklet_status: 'final_ready',
			template_id: 'guided-concept-path',
			section_count: 1,
			document_section_count: 1,
			report_json: {},
			native_whole_lesson: true,
			document_contract_version: 2,
			visual_quality: {
				flagged: [
					{
						request_id: 'request-1',
						block_id: 'figure-1',
						status: 'flagged_quality',
						reasons: ['labels are faint']
					}
				],
				flagged_count: 1,
				failed_request_ids: [],
				retryable: true
			},
			created_at: null,
			completed_at: null
		};
		const refreshedDetail = {
			...flaggedDetail,
			visual_quality: { flagged: [], flagged_count: 0, failed_request_ids: [], retryable: false }
		};
		getV3GenerationDetail.mockReset();
		getV3GenerationDetail.mockResolvedValueOnce(flaggedDetail).mockResolvedValueOnce(refreshedDetail);
		fetchV3Document.mockReset();
		fetchV3Document.mockResolvedValue(pageDocumentV2Fixture);
		retryNativeVisuals.mockResolvedValue(undefined);

		render(CompletedV3GenerationPage);

		expect(await screen.findByTestId('visual-quality-warning')).toBeTruthy();
		await screen.findByRole('button', { name: 'Retry visuals' }).then(async (button) => {
			await button.click();
		});
		await waitFor(() => expect(retryNativeVisuals).toHaveBeenCalledWith('gen-123'));
		await waitFor(() => expect(getV3GenerationDetail).toHaveBeenCalledTimes(2));
		expect(screen.queryByTestId('visual-quality-warning')).toBeNull();
	});

	it('does not expose visual retry for flagged visuals on a non-ready generation', async () => {
		getV3GenerationDetail.mockResolvedValueOnce({
			id: 'gen-123',
			subject: 'Science',
			title: 'Water cycle',
			status: 'completed',
			booklet_status: 'final_ready',
			template_id: 'guided-concept-path',
			section_count: 1,
			document_section_count: 1,
			report_json: {},
			visual_quality: {
				flagged: [{ request_id: 'request-1', status: 'flagged_quality' }],
				flagged_count: 1,
				failed_request_ids: [],
				retryable: true
			},
			created_at: null,
			completed_at: null
		});
		fetchV3Document.mockResolvedValueOnce(pageDocumentV2Fixture);

		render(CompletedV3GenerationPage);

		await screen.findByText(/Quadratic review|V2 page document/i);
		expect(screen.queryByTestId('visual-quality-warning')).toBeNull();
		expect(screen.queryByRole('button', { name: 'Retry flagged visuals' })).toBeNull();
	});

	it('keeps a native V2 document non-final while visuals are awaiting or failed', async () => {
		getV3GenerationDetail.mockResolvedValueOnce({
			id: 'gen-123',
			subject: 'Science',
			title: 'Water cycle',
			status: 'awaiting_visuals',
			booklet_status: 'final_ready',
			template_id: 'guided-concept-path',
			section_count: 5,
			document_section_count: 5,
			report_json: {},
			native_whole_lesson: true,
			document_contract_version: 2,
			visual_quality: {
				flagged: [],
				flagged_count: 0,
				failed_request_ids: ['request-1'],
				retryable: true
			},
			created_at: null,
			completed_at: null
		});
		fetchV3Document.mockResolvedValueOnce(pageDocumentV2Fixture);

		render(CompletedV3GenerationPage);

		expect(await screen.findByText(/V2 page document/i)).toBeTruthy();
		expect(await screen.findByText(/A required visual is still being processed/i)).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Export Unavailable' })).toHaveProperty('disabled', true);
		expect(screen.getByRole('button', { name: 'Retry visuals' })).toBeTruthy();
	});
});

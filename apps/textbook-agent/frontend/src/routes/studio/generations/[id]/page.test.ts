// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { pageState, getV3GenerationDetail, fetchV3Document, downloadV3GenerationPdf } = vi.hoisted(() => ({
	pageState: {
		params: { id: 'gen-123' },
		url: new URL('http://localhost/studio/generations/gen-123')
	},
	getV3GenerationDetail: vi.fn(),
	fetchV3Document: vi.fn(),
	downloadV3GenerationPdf: vi.fn()
}));

vi.mock('$app/state', () => ({
	page: pageState
}));

vi.mock('$lib/api/v3', () => ({
	getV3GenerationDetail,
	fetchV3Document,
	downloadV3GenerationPdf
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
});

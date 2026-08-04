import { describe, expect, it } from 'vitest';

import {
	countMissingVisuals,
	getBookletExportPolicy,
	getBookletPrintReadiness,
	getBookletStatusSummary,
	isBookletStatus
} from './v3-booklet';

describe('isBookletStatus', () => {
	it('accepts valid statuses and rejects unknown values', () => {
		expect(isBookletStatus('draft_ready')).toBe(true);
		expect(isBookletStatus('final_with_warnings')).toBe(true);
		expect(isBookletStatus('unknown')).toBe(false);
		expect(isBookletStatus(null)).toBe(false);
	});
});

describe('getBookletStatusSummary', () => {
	it('uses the runtime outcome copy for review-needed drafts', () => {
		expect(getBookletStatusSummary('draft_needs_review')).toBe(
			'Draft rendered, but major issues remain after review/repair.'
		);
	});
});

describe('getBookletExportPolicy', () => {
	it('enables final exports', () => {
		expect(getBookletExportPolicy('final_ready')).toMatchObject({
			enabled: true,
			requiresConfirm: false
		});
	});

	it('keeps review-needed drafts exportable without an extra confirm step', () => {
		expect(getBookletExportPolicy('draft_needs_review')).toMatchObject({
			enabled: true,
			requiresConfirm: false
		});
	});

	it('disables unusable drafts', () => {
		expect(getBookletExportPolicy('failed_unusable')).toMatchObject({
			enabled: false
		});
	});
});

describe('print readiness', () => {
	it('marks packs with no missing visuals as ready to print', () => {
		expect(
			getBookletPrintReadiness('final_ready', {
				section_diagnostics: [
					{
						section_id: 'intro',
						status: 'complete',
						renderable: true,
						missing_components: [],
						missing_visuals: [],
						warnings: []
					}
				]
			})
		).toMatchObject({
			label: 'Ready to print',
			imageState: 'complete'
		});
	});

	it('marks packs with missing visuals as text-only printable', () => {
		expect(
			getBookletPrintReadiness('draft_with_warnings', {
				section_diagnostics: [
					{
						section_id: 'model',
						status: 'incomplete',
						renderable: true,
						missing_components: [],
						missing_visuals: ['required_visual'],
						warnings: []
					}
				]
			})
		).toMatchObject({
			label: 'Text ready - images not complete (text-only print)',
			imageState: 'incomplete',
			missingVisualCount: 1
		});
	});

	it('counts missing visuals across all sections', () => {
		expect(
			countMissingVisuals({
				section_diagnostics: [
					{
						section_id: 'a',
						status: 'complete',
						renderable: true,
						missing_components: [],
						missing_visuals: ['required_visual'],
						warnings: []
					},
					{
						section_id: 'b',
						status: 'incomplete',
						renderable: true,
						missing_components: [],
						missing_visuals: ['required_visual', 'diagram_series'],
						warnings: []
					}
				]
			})
		).toBe(3);
	});
});

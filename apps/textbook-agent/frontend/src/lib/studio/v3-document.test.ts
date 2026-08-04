import { describe, expect, it } from 'vitest';

import { coerceV3DocumentToPack, deriveV3BookletStatus } from './v3-document';

describe('v3-document utilities', () => {
	it('derives fallback status when document has sections but no explicit status', () => {
		const status = deriveV3BookletStatus({ sections: [{ section_id: 's-1' }] }, 'final_ready');
		expect(status).toBe('final_ready');
	});

	it('coerces document payload into a V3 pack', () => {
		const pack = coerceV3DocumentToPack(
			'gen-1',
			{
				kind: 'v3_booklet_pack',
				template_id: 'guided-concept-path',
				status: 'final_ready',
				sections: [{ section_id: 's-1', header: { title: 'Intro' } }],
				warnings: ['warn'],
				section_diagnostics: [
					{
						section_id: 's-1',
						status: 'complete',
						renderable: true,
						missing_components: [],
						missing_visuals: [],
						warnings: []
					}
				],
				booklet_issues: []
			},
			{ templateId: 'guided-concept-path' }
		);

		expect(pack).not.toBeNull();
		expect(pack?.status).toBe('final_ready');
		expect(pack?.sections).toHaveLength(1);
		expect(pack?.section_diagnostics).toHaveLength(1);
	});
});

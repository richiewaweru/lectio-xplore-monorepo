import { describe, expect, it } from 'vitest';

import { v3PackToBuilderDocument } from './from-generation';

describe('v3PackToBuilderDocument', () => {
	it('adapts a v3 pack into a builder lesson document', () => {
		const lesson = v3PackToBuilderDocument(
			{
				generation_id: 'gen_123',
				template_id: 'guided-concept-path',
				subject: 'Fractions',
				status: 'final_ready',
				sections: [
					{
						section_id: 'section_1',
						template_id: 'guided-concept-path',
						header: {
							title: 'Fractions intro',
							subject: 'Fractions',
							grade_band: 'secondary'
						},
						hook: {
							headline: 'Why fractions matter'
						}
					}
				]
			},
			{ routeGenerationId: 'gen_123' }
		);

		expect(lesson.source).toBe('generated');
		expect(lesson.source_generation_id).toBe('gen_123');
		expect(lesson.subject).toBe('Fractions');
		expect(lesson.sections.length).toBe(1);
		expect(Object.keys(lesson.blocks).length).toBeGreaterThan(0);
	});

	it('maps incomplete diagnostics into unresolved section issues', () => {
		const lesson = v3PackToBuilderDocument({
			generation_id: 'gen-issues', subject: 'Math', sections: [{ section_id: 'orient', header: { title: 'Orient' } }],
			section_diagnostics: [{ section_id: 'orient', status: 'incomplete', renderable: true, missing_components: ['hook-card'], missing_visuals: [], warnings: ['Hook output is missing.'] }],
			booklet_issues: []
		});
		const section = lesson.sections[0] as typeof lesson.sections[0] & { meta?: { issues?: Array<Record<string, unknown>> } };
		expect(section.meta?.issues).toEqual([
			expect.objectContaining({ severity: 'major', kind: 'component_missing', message: 'Hook output is missing.', component_ref: 'hook-card@orient', resolved: false })
		]);
	});
});

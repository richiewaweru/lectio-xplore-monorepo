import { describe, expect, it, vi } from 'vitest';

vi.mock('lectio', () => ({
	fromSectionContents: (
		sections: Array<Record<string, unknown>>,
		metadata: { title: string; subject: string; preset_id: string; source_generation_id?: string }
	) => {
		const blocks: Record<string, Record<string, unknown>> = {};
		const documentSections = sections.map((section, index) => {
			const blockId = `header-${index}`;
			blocks[blockId] = { id: blockId, component_id: 'section-header', content: section.header ?? {}, position: 0 };
			return { id: section.section_id, title: String(section.section_id), template_id: 'guided-concept-path', position: index, block_ids: [blockId] };
		});
		return {
			version: 1, id: 'lesson', title: metadata.title, subject: metadata.subject,
			preset_id: metadata.preset_id, source: 'generated', source_generation_id: metadata.source_generation_id,
			sections: documentSections, blocks, media: {}, created_at: 'now', updated_at: 'now'
		};
	}
}));

import { partitionGenerationIssues, v3PackToBuilderDocument } from './from-generation';

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

	it('keeps deterministic resource projections compatible with the builder contract', () => {
		const lesson = v3PackToBuilderDocument({
			generation_id: 'composition-1',
			kind: 'resource_projection',
			projection: 'revision_sheet',
			projection_template_version: 'resource-projection.v1',
			template_id: 'guided-concept-path',
			subject: 'Science',
			status: 'final_ready',
			sections: [{
				section_id: 'projected-revision-1', template_id: 'guided-concept-path',
				header: { title: 'Plant revision', subject: 'Science', grade_band: 'primary' },
				summary: { items: [{ text: 'Leaves make food.' }] },
				_projection_source: { source_generation_id: 'source-1', path_lesson_revision: 3 }
			}]
		});

		expect(lesson.source_generation_id).toBe('composition-1');
		expect(lesson.sections).toHaveLength(1);
		expect(Object.keys(lesson.blocks)).toContain('header-0');
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

	it('matches dotted and numeric booklet issue targets to sections', () => {
		const partitioned = partitionGenerationIssues(
			{
				booklet_issues: [
					{ issue_id: 'close-issue', generated_ref: 'close.practice', category: 'clarity', message: 'Clarify practice.' },
					{ issue_id: 'build-issue', section_id: 'build1', category: 'visual_quality_flagged', message: 'Improve image.' }
				]
			},
			['close', 'build']
		);

		expect(partitioned.sectionIssues.close?.[0]?.id).toBe('close-issue');
		expect(partitioned.sectionIssues.build?.[0]?.id).toBe('build-issue');
	});

	it('uses visual attachment targets and keeps unkeyed issues at document level', () => {
		const partitioned = partitionGenerationIssues(
			{
				visual_blocks: [{ visual_id: 'vis-1', attaches_to: 'practice', mode: 'diagram' }],
				booklet_issues: [
					{ issue_id: 'visual-issue', repair_target_id: 'visual:vis-1', category: 'visual_quality_flagged', message: 'Improve image.' },
					{ issue_id: 'anchor-issue', category: 'anchor_drift', message: 'Anchor drifted.' }
				]
			},
			['practice']
		);

		expect(partitioned.sectionIssues.practice?.[0]).toEqual(
			expect.objectContaining({ id: 'visual-issue', visual_id: 'vis-1' })
		);
		expect(partitioned.sectionIssues.practice?.[0]?.repair_target_id).toBe('visual:vis-1');
		expect(partitioned.documentLevelIssues).toEqual([
			expect.objectContaining({ id: 'anchor-issue', kind: 'anchor_drift' })
		]);
	});

	it('preserves text repair targets from generation review issues', () => {
		const partitioned = partitionGenerationIssues(
			{
				booklet_issues: [{
					issue_id: 'practice-issue', section_id: 'practice',
					category: 'missing_planned_content', message: 'Expected two questions.',
					generated_ref: 'practice.practice.problems[0].question',
					repair_target_id: 'questions:practice'
				}]
			},
			['practice']
		);

		expect(partitioned.sectionIssues.practice?.[0]).toEqual(
			expect.objectContaining({
				generated_ref: 'practice.practice.problems[0].question',
				repair_target_id: 'questions:practice'
			})
		);
	});
});

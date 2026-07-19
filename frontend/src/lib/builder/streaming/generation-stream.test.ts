import type { LessonDocument } from 'lectio';
import { describe, expect, it } from 'vitest';

import {
	appendAbsentGenerationSections,
	isTerminalPackStatus
} from './generation-stream';

function document(sections: LessonDocument['sections'], blocks: LessonDocument['blocks'] = {}): LessonDocument {
	return {
		version: 1, id: 'doc', title: 'Lesson', subject: 'Math', preset_id: 'blue-classroom',
		source: 'generated', sections, blocks, media: {}, created_at: 'a', updated_at: 'a'
	};
}

const plan = [
	{ id: 's1', title: 'One', position: 0 },
	{ id: 's2', title: 'Two', position: 1 },
	{ id: 's3', title: 'Three', position: 2 }
];

describe('appendAbsentGenerationSections', () => {
	it('inserts absent sections and their blocks', () => {
		const local = document([]);
		const adapted = document(
			[{ id: 's1', title: 'One', template_id: 'open-canvas', position: 0, block_ids: ['b1'] }],
			{ b1: { id: 'b1', component_id: 'explanation-block', position: 0, content: { body: 'Generated' } } }
		);
		const merged = appendAbsentGenerationSections(local, adapted, plan);
		expect(merged.sections.map((section) => section.id)).toEqual(['s1']);
		expect(merged.blocks.b1?.content).toEqual({ body: 'Generated' });
	});

	it('never changes an existing locally edited section or block', () => {
		const existing = { id: 's1', title: 'Edited title', template_id: 'open-canvas', position: 0, block_ids: ['local-b1'] };
		const local = document([existing], {
			'local-b1': { id: 'local-b1', component_id: 'explanation-block', position: 0, content: { body: 'Teacher edit' } }
		});
		const adapted = document(
			[{ id: 's1', title: 'Generated title', template_id: 'open-canvas', position: 0, block_ids: ['generated-b1'] }],
			{ 'generated-b1': { id: 'generated-b1', component_id: 'explanation-block', position: 0, content: { body: 'Changed upstream' } } }
		);
		const merged = appendAbsentGenerationSections(local, adapted, plan);
		expect(merged).toBe(local);
		expect(merged.sections[0]).toBe(existing);
		expect(merged.blocks['local-b1']?.content).toEqual({ body: 'Teacher edit' });
		expect(merged.blocks['generated-b1']).toBeUndefined();
	});

	it('appends newly generated component types to an existing header-only section', () => {
		const local = document(
			[{ id: 's1', title: 'Teacher title', template_id: 'open-canvas', position: 0, block_ids: ['local-header'] }],
			{ 'local-header': { id: 'local-header', component_id: 'section-header', position: 0, content: { title: 'Teacher title' } } }
		);
		const adapted = document(
			[{ id: 's1', title: 'Generated title', template_id: 'open-canvas', position: 0, block_ids: ['generated-header', 'generated-hook', 'generated-explanation'] }],
			{
				'generated-header': { id: 'generated-header', component_id: 'section-header', position: 0, content: { title: 'Generated title' } },
				'generated-hook': { id: 'generated-hook', component_id: 'hook-hero', position: 1, content: { body: 'Hook' } },
				'generated-explanation': { id: 'generated-explanation', component_id: 'explanation-block', position: 2, content: { body: 'Explanation' } }
			}
		);

		const merged = appendAbsentGenerationSections(local, adapted, plan);

		expect(merged.sections[0].title).toBe('Teacher title');
		expect(merged.sections[0].block_ids).toEqual([
			'local-header',
			'generated-hook',
			'generated-explanation'
		]);
		expect(merged.blocks['local-header']?.content).toEqual({ title: 'Teacher title' });
		expect(merged.blocks['generated-header']).toBeUndefined();
		expect(merged.blocks['generated-hook']?.position).toBe(1);
		expect(merged.blocks['generated-explanation']?.position).toBe(2);
	});

	it('does not duplicate generated component occurrences on a later snapshot', () => {
		const initial = document(
			[{ id: 's1', title: 'One', template_id: 'open-canvas', position: 0, block_ids: ['header-1', 'hook-1'] }],
			{
				'header-1': { id: 'header-1', component_id: 'section-header', position: 0, content: { title: 'One' } },
				'hook-1': { id: 'hook-1', component_id: 'hook-hero', position: 1, content: { body: 'First hook' } }
			}
		);
		const later = document(
			[{ id: 's1', title: 'One', template_id: 'open-canvas', position: 0, block_ids: ['header-2', 'hook-2'] }],
			{
				'header-2': { id: 'header-2', component_id: 'section-header', position: 0, content: { title: 'One' } },
				'hook-2': { id: 'hook-2', component_id: 'hook-hero', position: 1, content: { body: 'Later hook' } }
			}
		);

		expect(appendAbsentGenerationSections(initial, later, plan)).toBe(initial);
	});

	it('uses plan positions when sections arrive out of order', () => {
		const section3 = { id: 's3', title: 'Three', template_id: 'open-canvas', position: 2, block_ids: [] };
		const afterSection3 = appendAbsentGenerationSections(document([]), document([section3]), plan);
		const section2 = { id: 's2', title: 'Two', template_id: 'open-canvas', position: 0, block_ids: [] };
		const afterSection2 = appendAbsentGenerationSections(afterSection3, document([section2, section3]), plan);
		expect([...afterSection2.sections].sort((a, b) => a.position - b.position).map((section) => section.id)).toEqual(['s2', 's3']);
		expect(afterSection2.sections.find((section) => section.id === 's3')).toBe(afterSection3.sections[0]);
	});
});

describe('generation polling completion', () => {
	it('recognizes terminal pack states', () => {
		expect(isTerminalPackStatus('final_with_warnings')).toBe(true);
		expect(isTerminalPackStatus('streaming_preview')).toBe(false);
	});
});

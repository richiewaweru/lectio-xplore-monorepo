import type { LessonDocument } from 'lectio';
import { describe, expect, it } from 'vitest';

import {
	allPlannedSectionsPresent,
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
	it('recognizes terminal states and complete plans', () => {
		expect(isTerminalPackStatus('final_with_warnings')).toBe(true);
		expect(isTerminalPackStatus('streaming_preview')).toBe(false);
		expect(allPlannedSectionsPresent(document(plan.map((p) => ({ ...p, template_id: 'open-canvas', block_ids: [] }))), plan)).toBe(true);
	});
});

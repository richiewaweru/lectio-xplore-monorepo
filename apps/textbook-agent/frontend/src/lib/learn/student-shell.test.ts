import { describe, expect, it } from 'vitest';
import type { LessonDocument } from '@lectio/learn';
import { buildStudentStages, clampStageIndex } from './student-shell';

function doc(sections: LessonDocument['sections']): LessonDocument {
	return {
		version: 1,
		id: 'lesson-1',
		title: 'Photosynthesis',
		subject: 'Biology',
		preset_id: 'blue-classroom',
		source: 'generated',
		sections,
		blocks: {},
		media: {},
		created_at: '2026-01-01T00:00:00.000Z',
		updated_at: '2026-01-01T00:00:00.000Z'
	};
}

describe('student shell stages', () => {
	it('builds deterministic ordered stages with learner labels', () => {
		const stages = buildStudentStages(
			doc([
				{
					id: 's2',
					template_id: 'open-canvas',
					block_ids: [],
					title: 'Practice',
					position: 1,
					assessment_mode: 'practice'
				},
				{
					id: 's1',
					template_id: 'guided-concept-path',
					block_ids: [],
					title: 'Explain',
					position: 0,
					learner_label: 'Start here'
				}
			])
		);
		expect(stages.map((s) => s.section.id)).toEqual(['s1', 's2']);
		expect(stages[0].label).toBe('Start here');
		expect(stages[1].assessment_mode).toBe('practice');
	});

	it('clamps stage index for compact phone nav', () => {
		expect(clampStageIndex(-1, 3)).toBe(0);
		expect(clampStageIndex(9, 3)).toBe(2);
		expect(clampStageIndex(1, 0)).toBe(0);
	});
});

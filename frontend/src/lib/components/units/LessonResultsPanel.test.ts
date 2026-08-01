// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
	getLessonActual: vi.fn(), getMarksSummary: vi.fn(), saveLessonActual: vi.fn(), saveMarks: vi.fn()
}));
vi.mock('$lib/api/units', () => api);

import LessonResultsPanel from './LessonResultsPanel.svelte';

const lesson = {
	id: 'lesson-1', concept_id: 'concept-1', concept_slug: 'plant.food', title: 'Plant food',
	objective: 'Explain plant food.', objective_hash: 'hash', prerequisites: [], external_prerequisites: [],
	must_establish: ['Leaves make food.'], exclusions: [], primary_knowledge_type: 'conceptual' as const,
	secondary_demand: null, knowledge_type_source: 'path_planner', merge_warning: false, position: 0,
	source: 'path_planner', teacher_edited: false, skipped: false, revision: 2, pack_id: 'generation-1'
};
const path = {
	id: 'path-1', unit_id: 'unit-1', version: 1, revision: 1, status: 'approved', generated_by: 'planner',
	merge_critic_results: [], prerequisite_risks: [], forward_verified: true, reaches_destination: true,
	completeness_note: null, approved_at: '2026-08-01', created_at: '2026-08-01', lessons: [lesson]
};
const summary = {
	path_lesson_id: lesson.id, group_id: null, revision: 0,
	items: [{ item_id: 'item-1', stem: 'Where is food made?', total_count: 0, option_counts: [
		{ option_id: 'A', text: 'Roots', count: 0, correct: false, misconception_id: 'soil-food' },
		{ option_id: 'B', text: 'Leaves', count: 0, correct: true, misconception_id: null }
	] }], misconceptions: [], unclaimed_distractor_count: 0, advisory: true as const,
	advisory_note: 'Aggregate counts suggest teaching follow-up; they do not diagnose individual learners.'
};

describe('LessonResultsPanel', () => {
	afterEach(() => { cleanup(); vi.clearAllMocks(); });

	it('records only aggregate option counts and labels summaries advisory', async () => {
		api.getLessonActual.mockResolvedValue(null);
		api.getMarksSummary.mockResolvedValue(summary);
		api.saveMarks.mockResolvedValue({ ...summary, revision: 1 });
		render(LessonResultsPanel, { props: { unitId: 'unit-1', path, lessons: [lesson], groups: null } });

		expect(await screen.findByText('Where is food made?')).toBeTruthy();
		expect(screen.getByText('Advisory summary')).toBeTruthy();
		expect(screen.getByText(/do not diagnose individual learners/i)).toBeTruthy();
		expect(screen.queryByText(/learner name/i)).toBeNull();
		await fireEvent.input(screen.getByLabelText('Where is food made? A count'), { target: { value: '9' } });
		await fireEvent.input(screen.getByLabelText('Where is food made? B count'), { target: { value: '2' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Save marks' }));
		expect(api.saveMarks).toHaveBeenCalledWith('unit-1', path, lesson, {
			marks_revision: 0, group_id: null,
			items: [{ item_id: 'item-1', option_counts: { A: 9, B: 2 } }]
		});
	});
});

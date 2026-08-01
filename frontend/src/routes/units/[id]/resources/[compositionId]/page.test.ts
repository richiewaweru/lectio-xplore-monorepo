// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

const getUnitResource = vi.hoisted(() => vi.fn());
vi.mock('$app/state', () => ({
	page: {
		params: { id: 'unit-1', compositionId: 'composition-1' },
		url: new URL('http://test/units/unit-1/resources/composition-1')
	}
}));
vi.mock('$lib/api/units', () => ({ getUnitResource }));

import ResourcePage from './+page.svelte';

describe('/units/[id]/resources/[compositionId]', () => {
	afterEach(cleanup);

	it('loads a saved projection into the Lectio resource surface', async () => {
		getUnitResource.mockResolvedValue({
			id: 'composition-1', unit_id: 'unit-1', path_version_id: 'path-1', path_version: 1,
			path_revision: 1, projection: 'unit_exam', status: 'ready', lesson_ids: ['lesson-1'],
			period_ids: ['period-1'], group_ids: ['group-core'], selected_component_refs: [],
			selected_item_ids: ['item-1'], include_keys: true, template_version: 'resource-projection.v1',
			source_snapshots: [], document: {
				generation_id: 'composition-1', template_id: 'guided-concept-path', subject: 'Science',
				status: 'final_ready', sections: [{
					section_id: 'question-1', template_id: 'guided-concept-path',
					header: { title: 'Projected assessment', subject: 'Science', grade_band: 'primary' },
					quiz: { question: 'Where is food made?', quiz_type: 'multiple-choice',
						options: [
						{ text: 'Roots', correct: false, explanation: 'Review.' },
						{ text: 'Leaves', correct: true, explanation: 'Correct.' }
					] }
				}],
				answer_key: {
					label: 'Shared diagnostic answer key',
					note: 'Confirm diagnostic hypotheses against learner reasoning.',
					entries: [{
						question_number: 1, question: 'Where is food made?',
						correct_answer: 'Leaves', correct_key: 'B', diagnostics: [{
							option_key: 'A', option_text: 'Roots', misconception_id: 'soil-food',
							misconception_label: 'Chose roots → consistent with a soil-food misconception.'
						}]
					}]
				}
			}
		});

		render(ResourcePage);
		expect(await screen.findByRole('button', { name: 'Print' })).toBeTruthy();
		expect(await screen.findByText('Where is food made?')).toBeTruthy();
	});
});

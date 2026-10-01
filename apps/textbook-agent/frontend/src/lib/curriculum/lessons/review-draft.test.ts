import { describe, expect, it } from 'vitest';
import {
	buildReviewDraftEdits,
	editableFieldsForDocument,
	fieldKey,
	issueLabel,
	issueNodeIds,
	issueSectionIds,
	type SharedLessonDocument
} from './review-draft';

function document(): SharedLessonDocument {
	return {
		schema_version: 1,
		id: 'doc-1',
		revision: 3,
		content_hash: 'a'.repeat(64),
		title: 'Photosynthesis',
		sections: [
			{
				id: 'section-1',
				title: 'Intro',
				position: 0,
				nodes: [
					{ id: 'node-1', kind: 'paragraph', display: { text: 'Plants make food.' }, accessibility: { description: '' } },
					{
						id: 'node-2',
						kind: 'callout',
						display: { tone: 'note', title: 'Key idea', body: 'Chlorophyll absorbs light.' },
						accessibility: { description: '' }
					},
					{
						id: 'node-3',
						kind: 'figure',
						display: { asset_id: 'asset-1', caption: 'A leaf' },
						accessibility: { alt_text: 'Close-up of a green leaf' }
					},
					{
						id: 'node-4',
						kind: 'list',
						display: { ordered: false, items: ['Sunlight', 'Water', 'CO2'] },
						accessibility: { description: '' }
					},
					{
						id: 'node-5',
						kind: 'table',
						display: { headers: ['Input', 'Output'], rows: [['Water', 'Oxygen']], caption: '' },
						accessibility: { description: '' }
					},
					{ id: 'anchor-1', kind: 'task_anchor', task_spec_id: 'task-1', teaching_block_id: 'block-1' }
				]
			}
		]
	};
}

describe('editableFieldsForDocument', () => {
	it('extracts one field per allowlisted text slot, skipping task anchors', () => {
		const fields = editableFieldsForDocument(document());
		const byKey = new Map(fields.map((field) => [field.key, field]));

		expect(byKey.get(fieldKey({ section_id: 'section-1', node_id: 'node-1', field: 'text' }))?.value).toBe(
			'Plants make food.'
		);
		expect(
			byKey.get(fieldKey({ section_id: 'section-1', node_id: 'node-2', field: 'callout_title' }))?.value
		).toBe('Key idea');
		expect(
			byKey.get(fieldKey({ section_id: 'section-1', node_id: 'node-2', field: 'callout_body' }))?.value
		).toBe('Chlorophyll absorbs light.');
		expect(
			byKey.get(fieldKey({ section_id: 'section-1', node_id: 'node-3', field: 'figure_caption' }))?.value
		).toBe('A leaf');
		expect(
			byKey.get(fieldKey({ section_id: 'section-1', node_id: 'node-3', field: 'figure_alt_text' }))?.value
		).toBe('Close-up of a green leaf');
		expect(
			byKey.get(
				fieldKey({ section_id: 'section-1', node_id: 'node-4', field: 'list_item_text', item_index: 1 })
			)?.value
		).toBe('Water');
		expect(
			byKey.get(
				fieldKey({
					section_id: 'section-1',
					node_id: 'node-5',
					field: 'table_cell_text',
					row_index: 0,
					column_index: 1
				})
			)?.value
		).toBe('Oxygen');

		// No field targets the task anchor node.
		expect(fields.some((field) => field.node_id === 'anchor-1')).toBe(false);
	});
});

describe('buildReviewDraftEdits', () => {
	it('includes only changed, non-blank fields', () => {
		const fields = editableFieldsForDocument(document());
		const values = new Map(fields.map((field) => [field.key, field.value]));

		const paragraphKey = fieldKey({ section_id: 'section-1', node_id: 'node-1', field: 'text' });
		values.set(paragraphKey, 'Plants make their own food through photosynthesis.');

		const captionKey = fieldKey({ section_id: 'section-1', node_id: 'node-3', field: 'figure_caption' });
		values.set(captionKey, '   ');

		const edits = buildReviewDraftEdits(fields, values);

		expect(edits).toHaveLength(1);
		expect(edits[0]).toEqual({
			section_id: 'section-1',
			node_id: 'node-1',
			field: 'text',
			value: 'Plants make their own food through photosynthesis.',
			item_index: undefined,
			row_index: undefined,
			column_index: undefined
		});
	});

	it('returns no edits when nothing changed', () => {
		const fields = editableFieldsForDocument(document());
		const values = new Map(fields.map((field) => [field.key, field.value]));
		expect(buildReviewDraftEdits(fields, values)).toEqual([]);
	});
});

describe('issueLabel', () => {
	it('maps known codes to plain language', () => {
		expect(issueLabel('answer_leakage')).toBe('Answer leakage');
		expect(issueLabel('progression_gap')).toBe('Progression gap');
	});

	it('falls back to the raw code for unknown codes', () => {
		expect(issueLabel('some_future_code')).toBe('some_future_code');
	});
});

describe('issue id helpers', () => {
	const issues = [
		{
			issue_code: 'answer_leakage',
			affected_section_id: 'section-1',
			affected_node_ids: ['node-1', 'node-2'],
			explanation: 'x',
			required_correction: 'y'
		},
		{
			issue_code: 'progression_gap',
			affected_section_id: 'section-2',
			affected_node_ids: [],
			explanation: 'x',
			required_correction: 'y'
		}
	];

	it('collects affected section ids', () => {
		expect(issueSectionIds(issues)).toEqual(new Set(['section-1', 'section-2']));
	});

	it('collects affected node ids across issues', () => {
		expect(issueNodeIds(issues)).toEqual(new Set(['node-1', 'node-2']));
	});
});

describe('task wording fields', () => {
	function withTasks(): SharedLessonDocument {
		return {
			schema_version: 1,
			id: 'doc',
			revision: 1,
			content_hash: 'h',
			title: 'Shadows',
			sections: [
				{
					id: 'confront',
					title: 'Confront',
					position: 0,
					nodes: [
						{ id: 'anchor-choice', kind: 'task_anchor', task_spec_id: 'task-choice' },
						{ id: 'anchor-order', kind: 'task_anchor', task_spec_id: 'task-order' }
					]
				}
			],
			tasks: [
				{
					id: 'task-choice',
					action: 'select-one',
					prompt: 'On that belief, how wide?',
					response: {
						type: 'single_choice',
						options: [
							{ id: 'a', text: 'Narrow' },
							{ id: 'b', text: 'Wide' }
						]
					},
					evaluation: { type: 'choice_keys', correct_keys: ['b'] },
					feedback: { correct: 'Yes.', by_option: { a: 'Look again.' } }
				},
				{
					id: 'task-order',
					action: 'order-items',
					prompt: 'Order the stages.',
					response: { type: 'ordered_items', items: ['A', 'B'] },
					feedback: null
				}
			]
		};
	}

	it('offers prompt, choice option text and feedback, never the answer key', () => {
		const fields = editableFieldsForDocument(withTasks());
		const choice = fields.filter((field) => field.node_id === 'anchor-choice');
		expect(choice.map((field) => [field.field, field.option_id ?? field.feedback_key ?? null])).toEqual([
			['task_prompt', null],
			['task_option_text', 'a'],
			['task_option_text', 'b'],
			['task_feedback_text', 'correct'],
			['task_feedback_text', 'by_option.a']
		]);
		expect(fields.some((field) => field.value === 'b' && field.field !== 'task_option_text')).toBe(false);
	});

	it('only offers the prompt when the displayed text is the answer key', () => {
		const order = editableFieldsForDocument(withTasks()).filter((field) => field.node_id === 'anchor-order');
		expect(order.map((field) => field.field)).toEqual(['task_prompt']);
	});

	it('builds task edits carrying option_id and feedback_key', () => {
		const fields = editableFieldsForDocument(withTasks());
		const values = new Map(fields.map((field) => [field.key, field.value]));
		const prompt = fields.find((field) => field.field === 'task_prompt' && field.node_id === 'anchor-choice')!;
		const option = fields.find((field) => field.option_id === 'a')!;
		const feedback = fields.find((field) => field.feedback_key === 'by_option.a')!;
		values.set(prompt.key, 'Predict the width the wall will actually show.');
		values.set(option.key, 'A narrow band');
		values.set(feedback.key, 'Check the grazing rays again.');
		const edits = buildReviewDraftEdits(fields, values);
		expect(edits).toEqual([
			expect.objectContaining({ field: 'task_prompt', node_id: 'anchor-choice' }),
			expect.objectContaining({ field: 'task_option_text', option_id: 'a', value: 'A narrow band' }),
			expect.objectContaining({ field: 'task_feedback_text', feedback_key: 'by_option.a' })
		]);
	});
});

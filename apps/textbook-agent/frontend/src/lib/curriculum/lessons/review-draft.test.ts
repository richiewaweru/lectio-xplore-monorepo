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

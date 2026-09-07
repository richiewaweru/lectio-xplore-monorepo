import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		title: {
			format: 'plain_text',
			description: 'Comparison grid title.',
			renderBehavior: 'Plain text.'
		},
		intro: {
			format: 'plain_text',
			description: 'Optional framing paragraph.',
			renderBehavior: 'Plain text.'
		},
		'columns[].id': {
			format: 'plain_text_short',
			description: 'Stable column identifier.',
			renderBehavior: 'Plain text key used for row mapping.',
			constraints: ['Keep ids stable and short.']
		},
		'columns[].title': {
			format: 'plain_text_short',
			description: 'Column heading.',
			renderBehavior: 'Plain text.'
		},
		'columns[].summary': {
			format: 'plain_text',
			description: 'Summary line for the column.',
			renderBehavior: 'Plain text.'
		},
		'columns[].detail': {
			format: 'plain_text',
			description: 'Optional expanded column detail.',
			renderBehavior: 'Plain text.'
		},
		'rows[].criterion': {
			format: 'plain_text_short',
			description: 'Row label for the compared criterion.',
			renderBehavior: 'Plain text.'
		},
		'rows[].values': {
			format: 'structured_array',
			description: 'Per-column cell values in column order.',
			renderBehavior: 'Plain text entries aligned to columns by index.'
		},
		'rows[].takeaway': {
			format: 'plain_text_short',
			description: 'Optional short synthesis for the row.',
			renderBehavior: 'Plain text.'
		},
		apply_prompt: {
			format: 'plain_text',
			description: 'Optional apply/synthesis prompt after the grid.',
			renderBehavior: 'Plain text.'
		}
	},
	componentConstraints: [
		'Each row.values array length must match the number of columns.',
		'Use stable column ids when referencing columns in downstream tooling.'
	]
} satisfies LectioContentContract;

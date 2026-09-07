import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		'cells[].label': {
			format: 'plain_text_short',
			description: 'Short label for the cell.',
			renderBehavior: 'Plain text.'
		},
		'cells[].value': {
			format: 'inline_markdown',
			description: 'Primary value text.',
			renderBehavior: 'Inline markdown.'
		},
		'cells[].note': {
			format: 'inline_markdown',
			description: 'Optional supporting note.',
			renderBehavior: 'Inline markdown.'
		},
		'cells[].highlight': {
			format: 'boolean',
			description: 'Optional emphasis flag for the cell.',
			renderBehavior: 'Toggles highlight styling when true.'
		}
	},
	componentConstraints: ['Keep each cell to a single insight; avoid long paragraphs per cell.']
} satisfies LectioContentContract;

import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		question: {
			format: 'inline_markdown',
			description: 'Question stem.',
			renderBehavior: 'Inline markdown.'
		},
		marks: {
			format: 'number',
			description: 'Optional point value.',
			renderBehavior: 'Numeric marks shown to learners when provided.'
		},
		lines: {
			format: 'number',
			description: 'Optional ruled line count for print.',
			renderBehavior: 'Print layout hint.'
		},
		mark_scheme: {
			format: 'block_markdown',
			description: 'Optional marking guidance for teachers or auto-graders.',
			renderBehavior: 'Block markdown rubric text.'
		}
	},
	componentConstraints: ['Keep mark_scheme aligned to the stated marks when both exist.']
} satisfies LectioContentContract;

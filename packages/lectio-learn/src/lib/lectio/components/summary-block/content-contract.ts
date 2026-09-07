import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		heading: {
			format: 'plain_text',
			description: 'Optional summary heading.',
			renderBehavior: 'Plain text.'
		},
		'items[].text': {
			format: 'inline_markdown',
			description: 'Bullet text for each take-away.',
			renderBehavior: 'Inline markdown.'
		},
		closing: {
			format: 'inline_markdown',
			description: 'Optional closing line after bullets.',
			renderBehavior: 'Inline markdown.'
		}
	},
	componentConstraints: ['Keep items tight and parallel in structure where possible.']
} satisfies LectioContentContract;

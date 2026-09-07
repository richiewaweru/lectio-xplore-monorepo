import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		body: {
			format: 'inline_markdown',
			description: 'Bridge narrative from this section to upcoming work.',
			renderBehavior: 'Inline markdown.'
		},
		next: {
			format: 'plain_text_short',
			description: 'Short label for what comes next.',
			renderBehavior: 'Plain text.'
		},
		preview: {
			format: 'plain_text',
			description: 'Optional preview blurb of the next chunk.',
			renderBehavior: 'Plain text.'
		},
		prerequisites: {
			format: 'structured_array',
			description: 'Optional short prerequisites the learner should recall.',
			renderBehavior: 'Plain text list items.'
		}
	},
	componentConstraints: ['Keep next concrete and short.']
} satisfies LectioContentContract;

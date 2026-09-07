import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		label: {
			format: 'plain_text',
			description: 'Optional strip heading.',
			renderBehavior: 'Plain text.'
		},
		'items[].concept': {
			format: 'plain_text',
			description: 'Named prerequisite concept.',
			renderBehavior: 'Plain text.'
		},
		'items[].refresher': {
			format: 'inline_markdown',
			description: 'Optional one-line refresher.',
			renderBehavior: 'Inline markdown.'
		}
	},
	componentConstraints: ['List only prerequisites the section truly depends on.']
} satisfies LectioContentContract;

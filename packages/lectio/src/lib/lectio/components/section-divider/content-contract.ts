import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		label: {
			format: 'plain_text',
			description: 'Short divider label between sections.',
			renderBehavior: 'Plain text.'
		}
	},
	componentConstraints: ['Use a concise transition label, not a second heading.']
} satisfies LectioContentContract;

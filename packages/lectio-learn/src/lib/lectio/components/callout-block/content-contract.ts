import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		variant: {
			format: 'enum',
			description: 'Callout tone (info, tip, warning, exam-tip, remember).',
			renderBehavior: 'Selects surface styling and iconography.'
		},
		heading: {
			format: 'plain_text',
			description: 'Optional short heading above the body.',
			renderBehavior: 'Plain text.'
		},
		body: {
			format: 'block_markdown',
			description: 'Primary callout body text.',
			renderBehavior: 'Block markdown with support for emphasis and short lists.'
		}
	},
	componentConstraints: ['Use headings sparingly; variant already carries tone.']
} satisfies LectioContentContract;

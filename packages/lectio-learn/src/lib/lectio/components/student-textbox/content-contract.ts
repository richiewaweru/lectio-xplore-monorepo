import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		prompt: {
			format: 'inline_markdown',
			description: 'Prompt for the written response.',
			renderBehavior: 'Inline markdown.'
		},
		lines: {
			format: 'number',
			description: 'Optional number of ruled lines for print layouts.',
			renderBehavior: 'Controls ruled line count, not screen layout height.'
		},
		label: {
			format: 'plain_text',
			description: 'Optional accessible label for the input.',
			renderBehavior: 'Plain text.'
		}
	},
	componentConstraints: ['Keep prompts concrete and tied to a single task.']
} satisfies LectioContentContract;

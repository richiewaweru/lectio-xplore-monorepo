import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		prompt: {
			format: 'block_markdown',
			description: 'Main interview framing prompt.',
			renderBehavior: 'Block markdown.'
		},
		audience: {
			format: 'plain_text_short',
			description: 'Who the interview voice represents.',
			renderBehavior: 'Plain text.'
		},
		follow_up: {
			format: 'block_markdown',
			description: 'Optional follow-up question block.',
			renderBehavior: 'Block markdown.'
		}
	},
	componentConstraints: ['Keep audience concrete and short.']
} satisfies LectioContentContract;

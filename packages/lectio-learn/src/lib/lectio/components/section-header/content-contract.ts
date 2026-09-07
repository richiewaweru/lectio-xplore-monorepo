import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		title: {
			format: 'plain_text',
			description: 'Primary section title.',
			renderBehavior: 'Plain text heading.'
		},
		subtitle: {
			format: 'inline_markdown',
			description: 'Optional subtitle line.',
			renderBehavior: 'Inline markdown.'
		},
		subject: {
			format: 'plain_text',
			description: 'Subject label for the section.',
			renderBehavior: 'Plain text.'
		},
		section_number: {
			format: 'plain_text',
			description: 'Optional numeric or ordinal section label.',
			renderBehavior: 'Plain text chip.'
		},
		grade_band: {
			format: 'enum',
			description: 'Audience level band for the section.'
		},
		objectives: {
			format: 'structured_array',
			description: 'Optional learning objective strings.',
			renderBehavior: 'Plain text bullet lines.'
		},
		level_pills: {
			format: 'structured_array',
			description: 'Optional difficulty pills with labels.',
			renderBehavior: 'Structured items with label and warm/medium/cold variant.'
		}
	},
	componentConstraints: ['Keep title concise; subtitle optional for tonal context.']
} satisfies LectioContentContract;

import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		misconception: {
			format: 'plain_text_short',
			description: 'Names the misconception briefly.',
			renderBehavior: 'Plain text lead line.'
		},
		correction: {
			format: 'inline_markdown',
			description: 'Direct correction of the misconception.',
			renderBehavior: 'Inline markdown.'
		},
		why: {
			format: 'inline_markdown',
			description: 'Why the correction matters.',
			renderBehavior: 'Inline markdown.'
		},
		example: {
			format: 'inline_markdown',
			description: 'Single optional illustrative example.',
			renderBehavior: 'Inline markdown.'
		},
		examples: {
			format: 'structured_array',
			description: 'Optional list of illustrative examples.',
			renderBehavior: 'Inline markdown entries when multiple examples are needed.'
		},
		severity: {
			format: 'enum',
			description: 'Relative severity tag (minor or major).'
		},
		label: {
			format: 'plain_text_short',
			description: 'Header label for the pitfall box.',
			renderBehavior:
				'Rendered as a bold heading inside the alert box. Defaults to "Common Misconception" when absent.',
			constraints: ['Keep to 3 words or fewer.']
		}
	},
	componentConstraints: [
		'Correction should directly address the misconception line.',
		'Prefer examples[] when you need more than one short illustration.'
	]
} satisfies LectioContentContract;

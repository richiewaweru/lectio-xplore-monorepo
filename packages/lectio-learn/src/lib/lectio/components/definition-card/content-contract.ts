import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		term: {
			format: 'plain_text',
			description: 'The defined term as a heading.',
			renderBehavior: 'Plain text heading.'
		},
		plain: {
			format: 'inline_markdown',
			description: 'Student-friendly definition in plain language.',
			renderBehavior: 'Inline markdown.'
		},
		formal: {
			format: 'inline_markdown',
			description: 'More precise or formal definition.',
			renderBehavior: 'Inline markdown.'
		},
		notation: {
			format: 'latex_raw',
			description: 'Mathematical notation line when applicable.',
			constraints: [
				'Use raw LaTeX for heavy notation.',
				'If content is mostly prose, prefer inline_markdown stored elsewhere instead.'
			]
		},
		symbol: {
			format: 'plain_text',
			description: 'Short symbol label when relevant.',
			renderBehavior: 'Plain text.'
		},
		examples: {
			format: 'structured_array',
			description: 'Short example strings illustrating usage.',
			renderBehavior: 'Rendered as plain example lines (no extra quotes added by contract).'
		},
		related_terms: {
			format: 'structured_array',
			description: 'Related vocabulary references.',
			renderBehavior: 'Plain text entries.'
		},
		etymology: {
			format: 'inline_markdown',
			description: 'Optional etymology note.',
			renderBehavior: 'Inline markdown.'
		}
	},
	componentConstraints: [
		'plain should read approachable; formal should be more precise.',
		'Do not wrap examples in quotation marks if the renderer already decorates them.'
	]
} satisfies LectioContentContract;

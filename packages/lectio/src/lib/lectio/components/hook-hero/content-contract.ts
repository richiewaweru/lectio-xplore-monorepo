import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		headline: {
			format: 'plain_text',
			description: 'Short attention-grabbing headline.',
			renderBehavior: 'Plain text heading.'
		},
		body: {
			format: 'inline_markdown',
			description: 'Primary hook narrative.',
			renderBehavior:
				'Usually inline markdown. When type is quote, treat as plain quote text without markdown emphasis unless explicitly needed.'
		},
		anchor: {
			format: 'plain_text_short',
			description: 'Short anchor tying the hook to the lesson concept.',
			renderBehavior: 'Plain text snippet.'
		},
		type: {
			format: 'enum',
			description: 'Hook presentation mode (prose, quote, question, data-point).',
			constraints: [
				'When type is question, provide question_options.',
				'When type is data-point, provide data_point.'
			]
		},
		question_options: {
			format: 'structured_array',
			description: 'Optional multiple choice stems for question hooks.',
			renderBehavior: 'Plain text entries per option.'
		},
		data_point: {
			format: 'structured_object',
			description: 'Structured numeric or textual evidence for data-point hooks.',
			renderBehavior: 'Rendered as a compact fact card when present.'
		},
		image: {
			format: 'structured_object',
			description: 'Optional inline illustration with url and alt text.',
			renderBehavior: 'Rendered as an inline image when present.'
		},
		svg_content: {
			format: 'plain_text',
			description: 'Optional inline SVG markup.',
			renderBehavior: 'Sanitized SVG inserted when present.',
			constraints: ['SVG must be trusted or sanitized.']
		},
		quote_attribution: {
			format: 'plain_text',
			description: 'Attribution line for quote hooks.',
			renderBehavior: 'Plain text.'
		}
	},
	componentConstraints: [
		'Anchor should be short and specific to the section concept.',
		'Match optional payloads to the selected hook type.'
	]
} satisfies LectioContentContract;

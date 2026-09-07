import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		body: {
			format: 'block_markdown',
			description: 'Main explanation text for the section.',
			renderBehavior: 'Rendered as block markdown. Supports markdown and LaTeX math.'
		},
		emphasis: {
			format: 'plain_phrase_list',
			description: 'Phrases highlighted inside the explanation body.',
			renderBehavior: 'Lectio highlights matching phrases in the body.',
			constraints: [
				'Use plain phrases.',
				'Do not use markdown in emphasis items.',
				'Each phrase should appear in body.',
				'Prefer key terms or short phrases, not full sentences.'
			]
		},
		callouts: {
			format: 'structured_array',
			description: 'Optional sideline notes with a tone tag and text.',
			renderBehavior: 'Displayed as optional notes associated with the explanation block.'
		}
	},
	componentConstraints: [
		'Put the primary teaching narrative in body.',
		'Use emphasis for concepts that should visually pop when they recur in body.'
	]
} satisfies LectioContentContract;

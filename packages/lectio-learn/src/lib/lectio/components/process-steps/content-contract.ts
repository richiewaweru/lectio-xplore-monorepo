import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		title: {
			format: 'plain_text',
			description: 'Title for the procedure.',
			renderBehavior: 'Plain text.'
		},
		intro: {
			format: 'inline_markdown',
			description: 'Optional introductory framing.',
			renderBehavior: 'Inline markdown.'
		},
		'steps[].number': {
			format: 'number',
			description: 'Step order index.',
			constraints: ['Numbers should be sequential.']
		},
		'steps[].action': {
			format: 'plain_text_short',
			description: 'Short verb-led action for the step.',
			renderBehavior: 'Plain text.'
		},
		'steps[].detail': {
			format: 'inline_markdown',
			description: 'Expanded explanation of the action.',
			renderBehavior: 'Inline markdown.'
		},
		'steps[].input': {
			format: 'plain_text_short',
			description: 'Short input label for the step.',
			renderBehavior: 'Plain text.'
		},
		'steps[].output': {
			format: 'plain_text_short',
			description: 'Short output label for the step.',
			renderBehavior: 'Plain text.'
		},
		'steps[].warning': {
			format: 'plain_text',
			description: 'Optional caution for the step.',
			renderBehavior: 'Plain text.'
		}
	},
	componentConstraints: [
		'Action should be short and verb-first.',
		'detail expands the action; input/output are labels, not paragraphs.'
	]
} satisfies LectioContentContract;

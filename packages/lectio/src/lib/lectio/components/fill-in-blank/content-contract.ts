import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		instruction: {
			format: 'plain_text',
			description: 'Leading instruction for the activity.',
			renderBehavior: 'Plain text.'
		},
		'segments[].text': {
			format: 'plain_text',
			description: 'Text chunk for a segment.',
			renderBehavior: 'Plain text segment content.'
		},
		'segments[].is_blank': {
			format: 'boolean',
			description: 'Whether this segment is rendered as a blank.',
			renderBehavior: 'Controls blank UI for the segment.'
		},
		'segments[].answer': {
			format: 'plain_text',
			description: 'Answer text when is_blank is true.',
			constraints: ['Required whenever is_blank is true.']
		},
		word_bank: {
			format: 'structured_array',
			description: 'Optional word bank entries.',
			renderBehavior: 'Plain text entries; should cover blank answers when provided.'
		}
	},
	componentConstraints: [
		'Alternate plain text segments with blanks as needed.',
		'Every blank segment should have an answer.',
		'If word_bank exists, include answers for all blanks.'
	]
} satisfies LectioContentContract;

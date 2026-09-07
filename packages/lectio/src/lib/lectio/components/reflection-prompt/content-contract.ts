import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		prompt: {
			format: 'inline_markdown',
			description: 'The reflective question or task.',
			renderBehavior: 'Inline markdown.'
		},
		type: {
			format: 'enum',
			description: 'Reflection mode (open, pair-share, sentence-stem, timed, etc.).',
			constraints: [
				'When type is sentence-stem, fill sentence_stem.',
				'When type is timed, set time_minutes.',
				'When type is pair-share, set pair_instruction.'
			]
		},
		space: {
			format: 'number_of_print_lines',
			description: 'Reserved vertical space for written responses when applicable.',
			renderBehavior: 'Controls print line affordance, not screen layout.'
		},
		sentence_stem: {
			format: 'plain_text',
			description: 'Starter clause when using sentence-stem mode.',
			renderBehavior: 'Plain text.'
		},
		time_minutes: {
			format: 'number',
			description: 'Duration guidance for timed reflections.',
			renderBehavior: 'Numeric minutes.'
		},
		pair_instruction: {
			format: 'plain_text',
			description: 'Pair-share facilitation line.',
			renderBehavior: 'Plain text.'
		}
	},
	componentConstraints: ['Choose optional fields that match the reflection type.']
} satisfies LectioContentContract;

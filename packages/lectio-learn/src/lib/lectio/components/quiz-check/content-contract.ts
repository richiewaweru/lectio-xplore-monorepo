import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		question: {
			format: 'inline_markdown',
			description: 'The quiz stem.',
			renderBehavior: 'Inline markdown with optional math.'
		},
		'options[].text': {
			format: 'inline_markdown',
			description: 'Visible option text shown to the learner.',
			renderBehavior: 'Inline markdown.'
		},
		'options[].explanation': {
			format: 'inline_markdown',
			description: 'Per-option rationale after answering.',
			renderBehavior: 'Inline markdown.'
		},
		'options[].correct': {
			format: 'boolean',
			description: 'Whether this option is the correct answer.'
		},
		'options[].diagnoses': {
			format: 'plain_text',
			description: 'Optional caller-supplied misconception id revealed by this option.',
			renderBehavior: 'Metadata only; never rendered in the learner-facing quiz.'
		},
		feedback_correct: {
			format: 'plain_text',
			description: 'Short feedback when the learner is correct.',
			renderBehavior: 'Plain text.'
		},
		feedback_incorrect: {
			format: 'plain_text',
			description: 'Short feedback when the learner is incorrect.',
			renderBehavior: 'Plain text.'
		},
		quiz_type: {
			format: 'enum',
			description: 'Optional quiz mode discriminator (multiple-choice vs true-false).'
		}
	},
	componentConstraints: [
		'Every option should include an explanation.',
		'Prefer exactly one correct option unless the quiz explicitly supports otherwise.',
		'Never generate, validate, or reinterpret a diagnoses id inside Lectio.',
		'Do not prefix option text with A/B/C labels in the string; the UI numbers options.'
	]
} satisfies LectioContentContract;
